#!/usr/bin/env python3
"""
Runs Jarvis action sequences.

  python3 actions.py           # "jarvis daddys home": play the startup Spotify
                                # playlist on repeat, start the AIM frontend dev
                                # server and open it in the browser, open a
                                # Claude agent terminal, then bring VS Code to
                                # the front (window order ends with VS Code on top).
  python3 actions.py --house   # "house": just play the "house music"
                                # Spotify playlist (assumes apps already open).

Both sequences raise the system volume first.
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
TRIGGER_VOLUME = 75  # loud, but leaves room for claps to still register over it


def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def run_applescript(script):
    subprocess.run(["osascript", "-e", script], check=False)


def set_trigger_volume():
    log(f"Setting system volume to {TRIGGER_VOLUME}")
    subprocess.run(["osascript", "-e", f"set volume output volume {TRIGGER_VOLUME}"], check=False)


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


def open_claude_agent():
    log("Opening Claude agent terminal in ~/AIM")
    script = f'''
    tell application "Terminal"
        activate
        do script "cd {AIM_DIR} && claude"
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
    set_trigger_volume()
    play_startup_playlist()
    start_frontend_and_open_browser()
    open_claude_agent()
    open_vscode()
    log("=== Trigger sequence complete ===")


def house():
    log("=== House command fired ===")
    set_trigger_volume()
    play_house_playlist()
    log("=== House command complete ===")


if __name__ == "__main__":
    if "--house" in sys.argv:
        house()
    else:
        main()
