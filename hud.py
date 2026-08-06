#!/usr/bin/env python3
"""
Jarvis HUD: two windows that pop up together when listener.py hears two
claps, and auto-hide a few seconds after the last update.

  - "control" window: small, functional, NOT click-through. Shows the status
    label and (in "active" state) the X close button.
  - "backdrop" window: large, purely decorative, click-through (so it never
    blocks interacting with whatever's underneath), mirrors the same state
    with a bigger animation.

listener.py drives both by writing JSON to STATE_FILE:
  {"state": "listening", "text": "", "ts": <time.time()>}
  {"state": "heard", "text": "<command or transcript>", "ts": <time.time()>}

While the specific `claude` session launched by "activate"/"prompt"/"new
project" is running (tracked via CLAUDE_SESSION_PID_FILE, written by
actions.py) both windows stay open in a persistent "active" state, instead
of auto-hiding. This is scoped to that one PID rather than any `claude`
process system-wide, since matching broadly would also catch unrelated
sessions (e.g. a VS Code Claude Code extension chat). Clicking the control
window's X calls stop_listening() below, which pauses listener.py's clap
detection (via PAUSE_FILE) and hides both windows; a double clap in
listener.py clears the pause and lets them reappear.

This process is standalone (not imported by listener.py) because pywebview's
event loop must own the main thread.
"""
import json
import os
import time
import webview
from webview.platforms.cocoa import BrowserView
from PyObjCTools import AppHelper

STATE_FILE = os.path.expanduser("~/.jarvis/hud_state.json")
HTML_FILE = os.path.expanduser("~/.jarvis/hud.html")
BACKDROP_HTML_FILE = os.path.expanduser("~/.jarvis/hud_backdrop.html")
PAUSE_FILE = os.path.expanduser("~/.jarvis/paused")
CLAUDE_SESSION_PID_FILE = os.path.expanduser("~/.jarvis/claude_session.pid")
POLL_INTERVAL = 0.15
HIDE_AFTER = 3.5  # seconds since the last state update before auto-hiding


def read_state():
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"state": "idle", "text": "", "ts": 0}


def is_paused():
    return os.path.exists(PAUSE_FILE)


def claude_session_active():
    try:
        with open(CLAUDE_SESSION_PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, 0)  # raises if that pid isn't alive
        return True
    except (FileNotFoundError, ValueError, ProcessLookupError, PermissionError):
        return False


def make_click_through(window):
    for _ in range(50):
        if window.uid in BrowserView.instances:
            break
        time.sleep(0.1)
    native = BrowserView.instances[window.uid].window
    # setIgnoresMouseEvents_ is a raw AppKit call and must run on the main
    # thread; poll_loop runs in a background thread, so dispatch it there.
    AppHelper.callAfter(native.setIgnoresMouseEvents_, True)


class HudApi:
    def __init__(self):
        self.control = None
        self.backdrop = None

    def stop_listening(self):
        with open(PAUSE_FILE, "w") as f:
            f.write("1")
        if self.control:
            self.control.hide()
        if self.backdrop:
            self.backdrop.hide()
        return True


def poll_loop(control, backdrop):
    make_click_through(backdrop)

    last_ts = None
    shown = False
    active_mode = False

    def show_both():
        control.show()
        backdrop.show()

    def hide_both():
        control.hide()
        backdrop.hide()

    def set_state(state, text=""):
        control.evaluate_js(f"setHudState({json.dumps(state)}, {json.dumps(text)})")
        backdrop.evaluate_js(f"setBackdropState({json.dumps(state)})")

    while True:
        paused = is_paused()
        session_active = (not paused) and claude_session_active()

        if session_active:
            if not active_mode:
                active_mode = True
                set_state("active", "CLAUDE SESSION ACTIVE")
                show_both()
                shown = True
            time.sleep(POLL_INTERVAL)
            continue
        elif active_mode:
            active_mode = False
            set_state("idle")
            hide_both()
            shown = False

        if paused:
            time.sleep(POLL_INTERVAL)
            continue

        data = read_state()
        ts = data.get("ts", 0)
        age = time.time() - ts

        if ts != last_ts and age < HIDE_AFTER:
            last_ts = ts
            set_state(data.get("state", "idle"), data.get("text", ""))
            if not shown:
                show_both()
                shown = True
        elif shown and age >= HIDE_AFTER:
            set_state("idle")
            hide_both()
            shown = False

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    api = HudApi()

    # Created first so it becomes pywebview's "master" window.
    backdrop = webview.create_window(
        "Jarvis Backdrop",
        BACKDROP_HTML_FILE,
        width=1300,
        height=900,
        frameless=True,
        on_top=True,
        transparent=True,
        hidden=True,
        resizable=False,
    )
    control = webview.create_window(
        "Jarvis HUD",
        HTML_FILE,
        width=340,
        height=340,
        frameless=True,
        easy_drag=True,
        on_top=True,
        transparent=True,
        hidden=True,
        js_api=api,
    )
    api.control = control
    api.backdrop = backdrop
    webview.start(poll_loop, (control, backdrop))
