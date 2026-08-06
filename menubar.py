#!/usr/bin/env python3
"""
Jarvis menu bar toggle: a status bar item to fully turn mic capture on/off,
for when you don't want Jarvis's mic listening at all (privacy, meetings,
etc). Distinct from the HUD's X button / saying "stop", which only pause
until the next double clap and leave the mic actively sampling so it can
hear that clap. Toggling this off closes listener.py's InputStream outright;
toggling back on is the only way to resume (no clap will be heard).

Standalone process, launched by listener.py alongside hud.py.
"""
import os
import rumps

MIC_OFF_FILE = os.path.expanduser("~/.jarvis/mic_off")


class JarvisMenuBar(rumps.App):
    def __init__(self):
        super().__init__("🎙", quit_button="Quit Jarvis Listener")
        self.toggle_item = rumps.MenuItem("", callback=self.toggle)
        self.menu = [self.toggle_item]
        self.refresh()

    def toggle(self, _sender):
        if os.path.exists(MIC_OFF_FILE):
            os.remove(MIC_OFF_FILE)
        else:
            with open(MIC_OFF_FILE, "w") as f:
                f.write("1")
        self.refresh()

    def refresh(self):
        off = os.path.exists(MIC_OFF_FILE)
        self.title = "🔇" if off else "🎙"
        self.toggle_item.title = "Turn Mic On" if off else "Turn Mic Off"


if __name__ == "__main__":
    JarvisMenuBar().run()
