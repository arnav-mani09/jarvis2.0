# jarvis2.0

Clap-twice + voice-trigger automation for macOS. Say "jarvis daddys home" after two claps to launch VS Code, start Spotify playback, and spin up the local dev server — plus several other voice commands (see `listener.py`'s COMMANDS list) — all via a background `launchd` listener using local clap detection + speech-to-text. A small floating HUD window pops up while it's listening.

## How it works

- `listener.py` runs continuously in the background (installed as a `launchd` LaunchAgent). It watches microphone input for two amplitude spikes ("claps") within ~1.2s of each other, then records a few seconds of audio and checks it against Google's speech-to-text API against a list of known command phrases.
- On a match, it hands off to `actions.py` to run that command (open apps, control Spotify, commit/push, etc).
- Saying "activate" instead of a fixed command records a longer free-form request and opens an interactive `claude` terminal in `~/AIM` with that request as the first message — a voice front-end for Claude Code.
- `hud.py` is a separate always-on-top, borderless window (via `pywebview`) that `listener.py` launches automatically and drives by writing state to `~/.jarvis/hud_state.json`. It shows a "LISTENING..." indicator on claps and briefly shows what was heard, then auto-hides.

## Setup

```bash
pip3 install sounddevice numpy SpeechRecognition pywebview
```

The "activate" command requires the `claude` CLI to be installed and on `PATH`.

Copy `com.arnav.jarvis-listener.plist` into `~/Library/LaunchAgents/`, then:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.arnav.jarvis-listener.plist
```

macOS will prompt for microphone and automation (Terminal/Spotify control) permissions on first run — grant both.

## Tuning

Run `python3 listener.py --calibrate` to see live mic levels and pick a good `CLAP_THRESHOLD`. Run `python3 listener.py --test-trigger` to fire the action sequence directly, without clapping or speaking.
