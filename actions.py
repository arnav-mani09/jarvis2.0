#!/usr/bin/env python3
"""
Runs Jarvis action sequences.

  python3 actions.py           # "jarvis daddys home": play the startup Spotify
                                # playlist on repeat, start the AIM frontend dev
                                # server and open it in the browser, then bring
                                # VS Code to the front (window order ends with
                                # VS Code on top; uses the Claude extension there
                                # instead of a separate terminal).
  python3 actions.py --house       # "house": just play the "house music"
                                    # Spotify playlist (assumes apps already open).
  python3 actions.py --volume-low  # "volume low": set Spotify's volume to 60%.
  python3 actions.py --volume-mid  # "volume mid": set Spotify's volume to 100%.
  python3 actions.py --mute        # "mute": mute Spotify's volume.
  python3 actions.py --pause       # "pause": pause Spotify playback.
  python3 actions.py --resume      # "resume": resume Spotify playback.
  python3 actions.py --push-changes  # "push changes": commit and push ~/AIM in a new Terminal window.

The "jarvis daddys home" and "house" sequences set Spotify's volume first.
"""
import sys
import os
import subprocess
import time

AIM_DIR = os.path.expanduser("~/AIM")
FRONTEND_DIR = os.path.join(AIM_DIR, "aim-app")
STARTUP_PLAYLIST_URI = "spotify:playlist:35V5c5pIglRr2wydBbHKsv"  # startup playlist
HOUSE_PLAYLIST_URI = "spotify:playlist:68StCidp9zYb7tPX3h99fM"  # "house music" playlist
FRONTEND_PORT = 3000
LOG_FILE = os.path.expanduser("~/.jarvis/logs/actions.log")
TRIGGER_VOLUME = 60  # loud, but leaves room for claps to still register over it
LOW_VOLUME = 60
MID_VOLUME = 100


def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def run_applescript(script):
    subprocess.run(["osascript", "-e", script], check=False)


def set_spotify_volume(level):
    log(f"Setting Spotify volume to {level}")
    script = f'''
    tell application "Spotify"
        set sound volume to {level}
    end tell
    '''
    run_applescript(script)


def open_vscode():
    log("Bringing VS Code to front")
    subprocess.run(["open", "-a", "Visual Studio Code"])


def play_startup_playlist():
    log("Launching Spotify and playing startup playlist on repeat")
    script = f'''
    tell application "Spotify"
        activate
        play track "{STARTUP_PLAYLIST_URI}"
        set repeating to true
    end tell
    '''
    run_applescript(script)


def play_house_playlist():
    log("Launching Spotify and playing 'house music' playlist")
    script = f'''
    tell application "Spotify"
        activate
        play track "{HOUSE_PLAYLIST_URI}"
    end tell
    '''
    run_applescript(script)


def port_in_use(port):
    result = subprocess.run(["lsof", f"-i:{port}", "-sTCP:LISTEN"], capture_output=True, text=True)
    return bool(result.stdout.strip())


def start_frontend_and_open_browser():
    if port_in_use(FRONTEND_PORT):
        log(f"Port {FRONTEND_PORT} already in use, assuming dev server is already running.")
    else:
        log("Starting Next.js dev server in a new Terminal tab.")
        script = f'''
        tell application "Terminal"
            activate
            do script "cd {FRONTEND_DIR} && npm run dev"
        end tell
        '''
        run_applescript(script)
        log(f"Waiting up to 30s for dev server on port {FRONTEND_PORT}...")
        for _ in range(30):
            if port_in_use(FRONTEND_PORT):
                break
            time.sleep(1)
    subprocess.run(["open", f"http://localhost:{FRONTEND_PORT}"])


def main():
    log("=== Trigger fired ===")
    set_spotify_volume(TRIGGER_VOLUME)
    play_startup_playlist()
    start_frontend_and_open_browser()
    open_vscode()
    log("=== Trigger sequence complete ===")


def house():
    log("=== House command fired ===")
    set_spotify_volume(TRIGGER_VOLUME)
    play_house_playlist()
    log("=== House command complete ===")


def volume_low():
    log("=== Volume low command fired ===")
    set_spotify_volume(LOW_VOLUME)
    log("=== Volume low command complete ===")


def volume_mid():
    log("=== Volume mid command fired ===")
    set_spotify_volume(MID_VOLUME)
    log("=== Volume mid command complete ===")


def mute():
    log("=== Mute command fired ===")
    set_spotify_volume(0)
    log("=== Mute command complete ===")


def pause():
    log("=== Pause command fired ===")
    run_applescript('tell application "Spotify" to pause')
    log("=== Pause command complete ===")


def resume():
    log("=== Resume command fired ===")
    run_applescript('tell application "Spotify" to play')
    log("=== Resume command complete ===")


def push_changes():
    log("=== Push changes command fired ===")
    commit_msg = f"Jarvis voice update {time.strftime('%Y-%m-%d %H:%M:%S')}"
    git_cmd = f"cd {AIM_DIR} && git add -A && git commit -m '{commit_msg}' && git push"
    script = f'''
    tell application "Terminal"
        activate
        do script "{git_cmd}"
    end tell
    '''
    run_applescript(script)
    log("=== Push changes command complete ===")


if __name__ == "__main__":
    if "--house" in sys.argv:
        house()
    elif "--volume-low" in sys.argv:
        volume_low()
    elif "--volume-mid" in sys.argv:
        volume_mid()
    elif "--mute" in sys.argv:
        mute()
    elif "--pause" in sys.argv:
        pause()
    elif "--resume" in sys.argv:
        resume()
    elif "--push-changes" in sys.argv:
        push_changes()
    else:
        main()
