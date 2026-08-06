#!/usr/bin/env python3
"""
Jarvis trigger: listens for two claps followed by a spoken command, then
runs actions.py. Also drives a small floating HUD window (hud.py) that pops
up while listening and shows what was heard.

Commands (see COMMANDS below):
  "jarvis daddys home" -> full startup sequence (Spotify, dev server, VS Code)
  "house"              -> just play the "house music" Spotify playlist
  "drake"              -> just play the Drake Spotify playlist
  "volume low"         -> set Spotify's volume to 60%
  "volume mid"         -> set Spotify's volume to 100%
  "mute"               -> mute Spotify's volume
  "pause"              -> pause Spotify playback
  "resume"             -> resume Spotify playback
  "push changes"       -> commit and push ~/AIM in a new Terminal window
  "claude"             -> open (or focus) an interactive Claude terminal (~/AIM)
  "new project"        -> tell that Claude session to start a new project
  "activate"/"prompt"  -> records a follow-up request and sends it to that
                           same Claude session (opening one first if needed)
Saying "stop" during the phrase check cancels the pending command.

Two ways to stop listening:
  - Say "stop" mid-phrase, or click the HUD's X button, to pause until the
    next double clap (mic keeps sampling so it can hear that clap).
  - Toggle the menu bar item off to fully stop mic capture (see menubar.py).

Modes:
  python3 listener.py                # normal background listening
  python3 listener.py --calibrate    # print live mic levels to help pick CLAP_THRESHOLD
  python3 listener.py --test-trigger # skip listening, just run the default action sequence once
"""
import json
import os
import sys
import time
import queue
import subprocess
import numpy as np
import sounddevice as sd
import speech_recognition as sr

SAMPLE_RATE = 16000
BLOCK_SIZE = 1024

# --- Tunables. Run `--calibrate` and adjust these based on what you see. ---
CLAP_THRESHOLD = 0.2         # RMS level (0-1ish) a clap must exceed
CLAP_MIN_GAP = 0.12          # min seconds between two claps (avoid double-count of one clap's echo)
CLAP_MAX_GAP = 1.2           # max seconds between the two claps
PHRASE_RECORD_SECONDS = 3.0  # how long to record after claps, to catch the spoken phrase
COMMAND_RECORD_SECONDS = 6.0  # how long to record the free-form request after "activate"
TRIGGER_COOLDOWN = 3         # seconds to ignore claps after a successful trigger (avoids re-triggering off the same clap/noise burst)

CANCEL_TOKEN = "stop"  # saying this during the phrase check aborts the trigger
# Command names that trigger the two-stage "record a follow-up request" flow.
SMART_SEND_NAMES = {"activate", "prompt"}

# Each command's tokens must ALL appear (substring match) in the transcript.
# Checked in order; the first full match wins.
COMMANDS = [
    {"name": "daddys_home", "tokens": ["jarvis", "daddy", "home"], "args": []},
    {"name": "house", "tokens": ["house"], "args": ["--house"]},
    {"name": "drake", "tokens": ["drake"], "args": ["--drake"]},
    {"name": "volume_low", "tokens": ["volume", "low"], "args": ["--volume-low"]},
    {"name": "volume_mid", "tokens": ["volume", "mid"], "args": ["--volume-mid"]},
    {"name": "mute", "tokens": ["mute"], "args": ["--mute"]},
    {"name": "pause", "tokens": ["pause"], "args": ["--pause"]},
    {"name": "resume", "tokens": ["resume"], "args": ["--resume"]},
    {"name": "push_changes", "tokens": ["push", "changes"], "args": ["--push-changes"]},
    {"name": "new_project", "tokens": ["new", "project"], "args": ["--new-project"]},
    {"name": "claude", "tokens": ["claude"], "args": ["--open-claude"]},
    {"name": "activate", "tokens": ["activate"], "args": []},
    {"name": "prompt", "tokens": ["prompt"], "args": []},
]

ACTIONS_SCRIPT = "/Users/arnavmani/.jarvis/actions.py"
HUD_SCRIPT = "/Users/arnavmani/.jarvis/hud.py"
MENUBAR_SCRIPT = "/Users/arnavmani/.jarvis/menubar.py"
LOG_FILE = "/Users/arnavmani/.jarvis/logs/listener.log"
HUD_LOG_FILE = "/Users/arnavmani/.jarvis/logs/hud.log"
MENUBAR_LOG_FILE = "/Users/arnavmani/.jarvis/logs/menubar.log"
HUD_STATE_FILE = "/Users/arnavmani/.jarvis/hud_state.json"
HUD_PID_FILE = "/Users/arnavmani/.jarvis/hud.pid"
MENUBAR_PID_FILE = "/Users/arnavmani/.jarvis/menubar.pid"
PAUSE_FILE = "/Users/arnavmani/.jarvis/paused"  # HUD's X button / "stop" creates this; a double clap clears it
MIC_OFF_FILE = "/Users/arnavmani/.jarvis/mic_off"  # menu bar toggle; fully stops mic capture until toggled back on


def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def rms(block):
    return float(np.sqrt(np.mean(np.square(block))))


def record_seconds(seconds):
    frames = sd.rec(int(seconds * SAMPLE_RATE), samplerate=SAMPLE_RATE, channels=1, dtype="float32")
    sd.wait()
    return frames.flatten()


def is_paused():
    return os.path.exists(PAUSE_FILE)


def clear_pause():
    try:
        os.remove(PAUSE_FILE)
    except FileNotFoundError:
        pass


def write_hud_state(state, text=""):
    try:
        with open(HUD_STATE_FILE, "w") as f:
            json.dump({"state": state, "text": text, "ts": time.time()}, f)
    except OSError:
        pass


def hud_already_running():
    try:
        with open(HUD_PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)  # raises if that pid isn't alive
        return True
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        return False


def ensure_hud_running():
    if hud_already_running():
        return
    log("Starting HUD.")
    with open(HUD_LOG_FILE, "a") as hud_log:
        proc = subprocess.Popen([sys.executable, HUD_SCRIPT], stdout=hud_log, stderr=hud_log)
    with open(HUD_PID_FILE, "w") as f:
        f.write(str(proc.pid))


def menubar_already_running():
    try:
        with open(MENUBAR_PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)
        return True
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        return False


def ensure_menubar_running():
    if menubar_already_running():
        return
    log("Starting menu bar toggle.")
    with open(MENUBAR_LOG_FILE, "a") as mb_log:
        proc = subprocess.Popen([sys.executable, MENUBAR_SCRIPT], stdout=mb_log, stderr=mb_log)
    with open(MENUBAR_PID_FILE, "w") as f:
        f.write(str(proc.pid))


def find_matching_command(text):
    t = text.lower()
    for cmd in COMMANDS:
        if all(tok in t for tok in cmd["tokens"]):
            return cmd
    return None


def record_and_transcribe(seconds):
    """Records `seconds` of audio and returns the transcript, or None if unrecognized."""
    audio = record_seconds(seconds)
    int16 = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    audio_data = sr.AudioData(int16.tobytes(), SAMPLE_RATE, 2)
    recognizer = sr.Recognizer()
    try:
        text = recognizer.recognize_google(audio_data)
        log(f"Heard: {text!r}")
        return text
    except sr.UnknownValueError:
        log("Could not understand audio")
        return None
    except sr.RequestError as e:
        log(f"Speech recognition service error: {e}")
        return None


def try_recognize_phrase():
    """Returns a matched command dict, "cancel", or None."""
    log("Two claps detected, recording for phrase check...")
    write_hud_state("listening")
    text = record_and_transcribe(PHRASE_RECORD_SECONDS)
    if text is None:
        write_hud_state("heard", "didn't catch that")
        return None
    if CANCEL_TOKEN in text.lower():
        write_hud_state("heard", "cancelled")
        return "cancel"
    cmd = find_matching_command(text)
    write_hud_state("heard", cmd["name"] if cmd else "no match")
    return cmd


def listen_for_request():
    """After "activate", records a longer free-form request. Returns text or None."""
    log("Activate heard, recording your request...")
    write_hud_state("listening")
    text = record_and_transcribe(COMMAND_RECORD_SECONDS)
    write_hud_state("heard", text if text else "didn't catch that")
    return text


def fire_trigger(cmd, extra_args=None):
    log(f"Command matched ({cmd['name']}). Firing trigger actions.")
    subprocess.Popen([sys.executable, ACTIONS_SCRIPT] + cmd["args"] + (extra_args or []))


def is_mic_off():
    return os.path.exists(MIC_OFF_FILE)


def calibrate():
    print("Calibration mode. Make sounds (claps, talking, silence) and watch the levels.")
    print("Pick a CLAP_THRESHOLD comfortably above your room's silence/talk noise but below a real clap.\n")

    def callback(indata, frames, time_info, status):
        level = rms(indata[:, 0])
        bar = "#" * int(level * 100)
        print(f"\rlevel={level:.3f} {bar:<50}", end="", flush=True)

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, blocksize=BLOCK_SIZE, callback=callback):
        while True:
            time.sleep(0.05)


def listen_loop():
    log("Listener started.")
    clear_pause()  # don't start up already paused from a stale file
    ensure_hud_running()
    ensure_menubar_running()
    signal_queue = queue.Queue()
    clap_times = []
    last_trigger_time = 0.0

    # NOTE: this callback runs on PortAudio's own audio thread, not the main
    # thread, so it can only communicate back via the thread-safe queue -
    # raising/catching exceptions across threads here would not work.
    def callback(indata, frames, time_info, status):
        now = time.time()
        if now - last_trigger_time < TRIGGER_COOLDOWN:
            return

        level = rms(indata[:, 0])
        if level < CLAP_THRESHOLD:
            return

        # debounce: ignore new peaks that are part of the same clap's decay
        if clap_times and now - clap_times[-1] < CLAP_MIN_GAP:
            return

        clap_times.append(now)
        while clap_times and now - clap_times[0] > CLAP_MAX_GAP:
            clap_times.pop(0)

        if len(clap_times) >= 2:
            clap_times.clear()
            signal_queue.put(True)

    mic_was_off = False
    while True:
        if is_mic_off():
            if not mic_was_off:
                log("Mic turned off via menu bar, mic capture stopped.")
                mic_was_off = True
            time.sleep(1)
            continue
        if mic_was_off:
            log("Mic turned back on via menu bar.")
            mic_was_off = False

        got_claps = False
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, blocksize=BLOCK_SIZE, callback=callback):
                while True:
                    if is_mic_off():
                        break  # `with` block below closes the stream
                    try:
                        signal_queue.get(timeout=1)
                        got_claps = True
                        break
                    except queue.Empty:
                        continue
        except Exception as e:
            log(f"Listener stream error, restarting in 2s: {e}")
            time.sleep(2)
            continue

        if not got_claps:
            continue  # stream closed because the mic was turned off, not because of claps

        if is_paused():
            clear_pause()
            log("Double clap while paused, resuming listening.")
            continue

        result = try_recognize_phrase()
        if result == "cancel":
            log("Heard 'stop', cancelling trigger and resuming listening.")
        elif result and result["name"] in SMART_SEND_NAMES:
            request_text = listen_for_request()
            if request_text:
                fire_trigger(result, extra_args=["--claude-request", request_text])
            else:
                log("No request captured, resuming listening.")
            last_trigger_time = time.time()
        elif result:
            fire_trigger(result)
            last_trigger_time = time.time()
        else:
            log("Phrase did not match, resuming listening.")


if __name__ == "__main__":
    if "--calibrate" in sys.argv:
        calibrate()
    elif "--test-trigger" in sys.argv:
        fire_trigger(COMMANDS[0])
        time.sleep(2)
    else:
        listen_loop()
