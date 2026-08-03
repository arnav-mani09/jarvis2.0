#!/usr/bin/env python3
"""
Runs the "jarvis daddys home" action sequence:
open VS Code on ~/AIM, play the Spotify track, open a Claude agent
terminal in ~/AIM, start the AIM frontend dev server and open it in
the browser.
"""
import os
import subprocess
import time

AIM_DIR = os.path.expanduser("~/AIM")
FRONTEND_DIR = os.path.join(AIM_DIR, "aim-app")
SPOTIFY_TRACK_URI = "spotify:track:5v98VA4TXznJNrw0XRphIb"  # Calvin Harris - I'm Not Alone (2019 Edit)
FRONTEND_PORT = 3000
LOG_FILE = os.path.expanduser("~/.jarvis/logs/actions.log")


def log(msg):
    line = f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG_FILE, "a") as f:
        f.write(line + "\n")


def run_applescript(script):
    subprocess.run(["osascript", "-e", script], check=False)


def open_vscode():
    log("Opening VS Code on ~/AIM")
    subprocess.run(["open", "-a", "Visual Studio Code", AIM_DIR])


def play_spotify_track():
    log("Launching Spotify and playing track")
    script = f'''
    tell application "Spotify"
        activate
        play track "{SPOTIFY_TRACK_URI}"
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
    open_vscode()
    play_spotify_track()
    open_claude_agent()
    start_frontend_and_open_browser()
    log("=== Trigger sequence complete ===")


if __name__ == "__main__":
    main()
