#!/usr/bin/env python3
"""
Jarvis trigger: listens for two claps followed by a spoken command, then
runs actions.py.

Commands (see COMMANDS below):
  "jarvis daddys home" -> full startup sequence (VS Code, Spotify, dev server, Claude terminal)
  "house"              -> just play the "house music" Spotify playlist
Saying "nevermind" during the phrase check cancels the pending command.

Modes:
  python3 listener.py                # normal background listening
  python3 listener.py --calibrate    # print live mic levels to help pick CLAP_THRESHOLD
  python3 listener.py --test-trigger # skip listening, just run the default action sequence once
"""
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
TRIGGER_COOLDOWN = 20        # seconds to ignore claps after a successful trigger

CANCEL_TOKEN = "nevermind"  # saying this during the phrase check aborts the trigger

# Each command's tokens must ALL appear (substring match) in the transcript.
# Checked in order; the first full match wins.
COMMANDS = [
    {"name": "daddys_home", "tokens": ["jarvis", "daddy", "home"], "args": []},
    {"name": "house", "tokens": ["house"], "args": ["--house"]},
]

ACTIONS_SCRIPT = "/Users/arnavmani/.jarvis/actions.py"
LOG_FILE = "/Users/arnavmani/.jarvis/logs/listener.log"


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


def find_matching_command(text):
    t = text.lower()
    for cmd in COMMANDS:
        if all(tok in t for tok in cmd["tokens"]):
            return cmd
    return None


def try_recognize_phrase():
    """Returns a matched command dict, "cancel", or None."""
    log("Two claps detected, recording for phrase check...")
    audio = record_seconds(PHRASE_RECORD_SECONDS)
    int16 = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    audio_data = sr.AudioData(int16.tobytes(), SAMPLE_RATE, 2)
    recognizer = sr.Recognizer()
    try:
        text = recognizer.recognize_google(audio_data)
        log(f"Heard: {text!r}")
        if CANCEL_TOKEN in text.lower():
            return "cancel"
        return find_matching_command(text)
    except sr.UnknownValueError:
        log("Could not understand audio")
        return None
    except sr.RequestError as e:
        log(f"Speech recognition service error: {e}")
        return None


def fire_trigger(cmd):
    log(f"Command matched ({cmd['name']}). Firing trigger actions.")
    subprocess.Popen([sys.executable, ACTIONS_SCRIPT] + cmd["args"])


def logs_terminal_already_open():
    result = subprocess.run(["pgrep", "-f", "tail -f .*listener.log"], capture_output=True, text=True)
    return bool(result.stdout.strip())


def open_log_terminal():
    if logs_terminal_already_open():
        return
    log("Opening log terminal window.")
    script = '''
    tell application "Terminal"
        activate
        do script "tail -f ~/.jarvis/logs/listener.log ~/.jarvis/logs/actions.log"
    end tell
    '''
    subprocess.run(["osascript", "-e", script], check=False)


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

    while True:
        try:
            with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, blocksize=BLOCK_SIZE, callback=callback):
                signal_queue.get()  # blocks until two claps are detected; stream closes on exit
        except Exception as e:
            log(f"Listener stream error, restarting in 2s: {e}")
            time.sleep(2)
            continue

        open_log_terminal()
        result = try_recognize_phrase()
        if result == "cancel":
            log("Heard 'nevermind', cancelling trigger and resuming listening.")
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
