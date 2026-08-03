# jarvis2.0

Clap-twice + voice-trigger automation for macOS. Say "jarvis daddys home" after two claps to launch VS Code, start Spotify playback, spin up the local dev server, and open a Claude Code session — all via a background `launchd` listener using local clap detection + speech-to-text.

## How it works

- `listener.py` runs continuously in the background (installed as a `launchd` LaunchAgent). It watches microphone input for two amplitude spikes ("claps") within ~1.2s of each other, then records a few seconds of audio and checks it against Google's speech-to-text API for the phrase "jarvis daddys home".
- On a match, it hands off to `actions.py`, which:
  - Opens VS Code on the target project folder
  - Plays a specific track on Spotify
  - Starts the project's local dev server (if not already running) and opens it in the browser
  - Opens a new terminal running the `claude` CLI in the project folder

## Setup

```bash
pip3 install sounddevice numpy SpeechRecognition
```

Copy `com.arnav.jarvis-listener.plist` into `~/Library/LaunchAgents/`, then:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.arnav.jarvis-listener.plist
```

macOS will prompt for microphone and automation (Terminal/Spotify control) permissions on first run — grant both.

## Tuning

Run `python3 listener.py --calibrate` to see live mic levels and pick a good `CLAP_THRESHOLD`. Run `python3 listener.py --test-trigger` to fire the action sequence directly, without clapping or speaking.
