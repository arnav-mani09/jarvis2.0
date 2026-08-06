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
  python3 actions.py --drake       # "drake": just play the Drake playlist
                                    # (assumes apps already open).
  python3 actions.py --volume-low  # "volume low": set Spotify's volume to 60%.
  python3 actions.py --volume-mid  # "volume mid": set Spotify's volume to 100%.
  python3 actions.py --mute        # "mute": mute Spotify's volume.
  python3 actions.py --pause       # "pause": pause Spotify playback.
  python3 actions.py --resume      # "resume": resume Spotify playback.
  python3 actions.py --push-changes  # "push changes": commit and push ~/AIM in a new Terminal window.
  python3 actions.py --open-claude              # "claude": opens ~/AIM's claude session, or
                                                 # brings it to front if one's already running.
  python3 actions.py --new-project              # "new project": tells that session to start
                                                 # a new project (opens one first if needed).
  python3 actions.py --claude-request "<text>"  # "activate"/"prompt": sends the transcribed
                                                 # request to that same session (opening one
                                                 # first if needed), as if you'd typed it.

The "jarvis daddys home" and "house" sequences set Spotify's volume first.

The claude commands track one session at a time via CLAUDE_SESSION_PID_FILE
and CLAUDE_WINDOW_ID_FILE. Sending text to an already-open session simulates
keystrokes via System Events, which needs a one-time Accessibility permission
grant (System Settings > Privacy & Security > Accessibility) for the python3
binary running this script.
"""
import sys
import os
import shlex
import subprocess
import time

AIM_DIR = os.path.expanduser("~/AIM")
FRONTEND_DIR = os.path.join(AIM_DIR, "aim-app")
STARTUP_PLAYLIST_URI = "spotify:playlist:35V5c5pIglRr2wydBbHKsv"  # startup playlist
HOUSE_PLAYLIST_URI = "spotify:playlist:68StCidp9zYb7tPX3h99fM"  # "house music" playlist
DRAKE_PLAYLIST_URI = "spotify:playlist:37i9dQZF1EIWR2Z7ggXEKn"  # Drake playlist
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


def applescript_escape(s):
    """Escape a string for embedding inside a double-quoted AppleScript string literal."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


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


def play_drake_playlist():
    log("Launching Spotify and playing Drake playlist")
    script = f'''
    tell application "Spotify"
        activate
        play track "{DRAKE_PLAYLIST_URI}"
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


def drake():
    log("=== Drake command fired ===")
    set_spotify_volume(TRIGGER_VOLUME)
    play_drake_playlist()
    log("=== Drake command complete ===")


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


CLAUDE_SESSION_PID_FILE = os.path.expanduser("~/.jarvis/claude_session.pid")
CLAUDE_WINDOW_ID_FILE = os.path.expanduser("~/.jarvis/claude_window.id")


def claude_session_active():
    try:
        with open(CLAUDE_SESSION_PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)  # raises if that pid isn't alive
        return True
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        return False


def open_new_claude_session(initial_text=None):
    log("Opening a new claude session in ~/AIM")
    shell_arg = shlex.quote(initial_text) if initial_text else ""
    # `exec` replaces the shell with claude in-place, keeping the same PID, so
    # the PID written here is claude's own PID (not some ambient claude
    # session elsewhere, like a VS Code extension chat) for the HUD to track.
    cmd = f"cd {AIM_DIR} && echo $$ > {CLAUDE_SESSION_PID_FILE} && exec claude {shell_arg}"
    script = f'''
    tell application "Terminal"
        activate
        do script "{applescript_escape(cmd)}"
        return id of window 1
    end tell
    '''
    result = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    window_id = result.stdout.strip()
    if window_id:
        with open(CLAUDE_WINDOW_ID_FILE, "w") as f:
            f.write(window_id)


def send_to_claude_session(text):
    log(f"Sending to existing claude session: {text!r}")
    try:
        with open(CLAUDE_WINDOW_ID_FILE) as f:
            window_id = f.read().strip()
    except FileNotFoundError:
        window_id = None
    if not window_id:
        log("No tracked window id, opening a new session instead")
        open_new_claude_session(text)
        return
    script = f'''
    tell application "Terminal"
        activate
        set index of window id {window_id} to 1
    end tell
    delay 0.3
    tell application "System Events"
        keystroke "{applescript_escape(text)}"
        key code 36
    end tell
    '''
    run_applescript(script)


def ensure_claude_session(initial_text):
    """Sends initial_text to the active session, or opens a new one with it as
    the first message."""
    if claude_session_active():
        send_to_claude_session(initial_text)
    else:
        open_new_claude_session(initial_text)


def open_claude():
    log("=== Claude command fired ===")
    if claude_session_active():
        log("Claude session already active, bringing it to front")
        try:
            with open(CLAUDE_WINDOW_ID_FILE) as f:
                window_id = f.read().strip()
            run_applescript(f'tell application "Terminal" to set index of window id {window_id} to 1')
        except FileNotFoundError:
            pass
    else:
        open_new_claude_session()
    log("=== Claude command complete ===")


def new_project():
    log("=== New project command fired ===")
    ensure_claude_session("Let's start a new project.")
    log("=== New project command complete ===")


def claude_request(request_text):
    log(f"=== Claude request command fired: {request_text!r} ===")
    ensure_claude_session(request_text)
    log("=== Claude request command complete ===")


if __name__ == "__main__":
    if "--house" in sys.argv:
        house()
    elif "--drake" in sys.argv:
        drake()
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
    elif "--open-claude" in sys.argv:
        open_claude()
    elif "--new-project" in sys.argv:
        new_project()
    elif "--claude-request" in sys.argv:
        claude_request(sys.argv[sys.argv.index("--claude-request") + 1])
    else:
        main()
