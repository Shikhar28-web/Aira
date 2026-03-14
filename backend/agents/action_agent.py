"""
AGENT 3 — ACTION AGENT
=======================
Executes system commands on the user's computer when the Brain Agent
detects a system-command intent.

Supported actions
-----------------
Application launchers:
    open_chrome, open_firefox, open_edge, open_vscode, open_notepad,
    open_calculator, open_file_explorer, open_task_manager, open_cmd,
    open_spotify

Power control:
    shutdown_system, restart_system

Volume control (Windows – simulates multimedia keys; Linux – amixer):
    volume_up, volume_down, volume_mute

Web search:
    web_search:<query string>

Every handler returns::

    {"ok": True | False, "message": "<human-readable Hindi/English update>"}
"""

import os
import platform
import subprocess
import threading
import time
import webbrowser
from typing import Any

SYSTEM = platform.system()   # "Windows" | "Linux" | "Darwin"


def _spawn(cmd: str | list, *, shell: bool = True) -> None:
    """Fire-and-forget subprocess (stderr/stdout discarded)."""
    subprocess.Popen(
        cmd,
        shell=shell,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


# ── Windows multimedia key codes ────────────────────────────────────────────
_VK_VOLUME_MUTE = 0xAD
_VK_VOLUME_DOWN = 0xAE
_VK_VOLUME_UP   = 0xAF


def _press_media_key(vk: int) -> None:
    """Simulate a Windows multimedia keypress via ctypes (no extra packages)."""
    import ctypes
    KEYEVENTF_KEYUP = 0x0002
    ctypes.windll.user32.keybd_event(vk, 0, 0, 0)
    ctypes.windll.user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


# ── Action Agent ─────────────────────────────────────────────────────────────

class ActionAgent:
    """Execute OS-level actions instructed by the Brain Agent."""

    # ── Public API ─────────────────────────────────────────────────────────

    def execute(self, action: str) -> dict[str, Any]:
        """
        Execute *action*.

        Args:
            action: Action name (e.g. ``"open_chrome"``) or
                    ``"web_search:<query>"`` for browser search.

        Returns:
            ``{"ok": bool, "message": "<status>"}``
        """
        if action and action.startswith("web_search:"):
            return self._web_search(action[len("web_search:"):].strip())

        handler = self._handler_map().get(action)
        if handler is None:
            return {"ok": False, "message": f"Unknown action: '{action}'"}

        try:
            return handler()
        except Exception as exc:
            print(f"[ActionAgent] Error executing '{action}': {exc}")
            return {"ok": False, "message": f"Action failed: {exc}"}

    # ── Handler registry ────────────────────────────────────────────────────

    def _handler_map(self) -> dict[str, Any]:
        return {
            # Apps
            "open_chrome":          self._open_chrome,
            "open_firefox":         self._open_firefox,
            "open_edge":            self._open_edge,
            "open_vscode":          self._open_vscode,
            "open_notepad":         self._open_notepad,
            "open_calculator":      self._open_calculator,
            "open_file_explorer":   self._open_file_explorer,
            "open_task_manager":    self._open_task_manager,
            "open_cmd":             self._open_cmd,
            "open_spotify":         self._open_spotify,
            # Power
            "shutdown_system":      self._shutdown,
            "restart_system":       self._restart,
            # Volume
            "volume_up":            self._volume_up,
            "volume_down":          self._volume_down,
            "volume_mute":          self._volume_mute,
        }

    # ── Application launchers ───────────────────────────────────────────────

    def _open_chrome(self):
        if SYSTEM == "Windows":
            _spawn("start chrome")
        elif SYSTEM == "Darwin":
            _spawn("open -a 'Google Chrome'")
        else:
            _spawn("google-chrome || chromium-browser")
        return {"ok": True, "message": "Chrome khola ja raha hai. (Opening Chrome)"}

    def _open_firefox(self):
        if SYSTEM == "Windows":
            _spawn("start firefox")
        elif SYSTEM == "Darwin":
            _spawn("open -a Firefox")
        else:
            _spawn("firefox")
        return {"ok": True, "message": "Firefox khola ja raha hai. (Opening Firefox)"}

    def _open_edge(self):
        if SYSTEM == "Windows":
            _spawn("start msedge")
        elif SYSTEM == "Darwin":
            _spawn("open -a 'Microsoft Edge'")
        else:
            _spawn("microsoft-edge")
        return {"ok": True, "message": "Edge browser khola ja raha hai. (Opening Edge)"}

    def _open_vscode(self):
        _spawn("code")
        return {"ok": True, "message": "VS Code khola ja raha hai. (Opening VS Code)"}

    def _open_notepad(self):
        if SYSTEM == "Windows":
            _spawn("notepad")
        elif SYSTEM == "Darwin":
            _spawn("open -a TextEdit")
        else:
            _spawn("gedit || xed || mousepad")
        return {"ok": True, "message": "Notepad khola ja raha hai. (Opening Notepad)"}

    def _open_calculator(self):
        if SYSTEM == "Windows":
            _spawn("calc")
        elif SYSTEM == "Darwin":
            _spawn("open -a Calculator")
        else:
            _spawn("gnome-calculator || kcalc")
        return {"ok": True, "message": "Calculator khola ja raha hai. (Opening Calculator)"}

    def _open_file_explorer(self):
        if SYSTEM == "Windows":
            _spawn("explorer")
        elif SYSTEM == "Darwin":
            _spawn("open .")
        else:
            _spawn("nautilus || thunar || dolphin")
        return {"ok": True, "message": "File Explorer khola ja raha hai. (Opening File Explorer)"}

    def _open_task_manager(self):
        if SYSTEM == "Windows":
            _spawn("taskmgr")
        elif SYSTEM == "Darwin":
            _spawn("open -a 'Activity Monitor'")
        else:
            _spawn("gnome-system-monitor || ksysguard")
        return {"ok": True, "message": "Task Manager khola ja raha hai. (Opening Task Manager)"}

    def _open_cmd(self):
        if SYSTEM == "Windows":
            _spawn("start cmd")
        elif SYSTEM == "Darwin":
            _spawn("open -a Terminal")
        else:
            _spawn(
                "x-terminal-emulator || gnome-terminal || xterm",
            )
        return {"ok": True, "message": "Terminal / Command Prompt khola ja raha hai."}

    def _open_spotify(self):
        if SYSTEM == "Windows":
            # Try installed Spotify first, then URI scheme
            spotify_exe = os.path.expandvars(
                r"%APPDATA%\Spotify\Spotify.exe"
            )
            if os.path.exists(spotify_exe):
                _spawn(f'"{spotify_exe}"')
            else:
                _spawn("start spotify:")
        elif SYSTEM == "Darwin":
            _spawn("open -a Spotify")
        else:
            _spawn("spotify || flatpak run com.spotify.Client")
        return {"ok": True, "message": "Spotify khola ja raha hai. (Opening Spotify)"}

    # ── Power controls ──────────────────────────────────────────────────────

    def _shutdown(self):
        def _do():
            time.sleep(2)
            if SYSTEM == "Windows":
                os.system("shutdown /s /t 1")
            else:
                os.system("shutdown -h now")

        threading.Thread(target=_do, daemon=True).start()
        return {
            "ok": True,
            "message": "System 2 second mein band ho raha hai. (Shutting down in 2 s)",
        }

    def _restart(self):
        def _do():
            time.sleep(2)
            if SYSTEM == "Windows":
                os.system("shutdown /r /t 1")
            else:
                os.system("reboot")

        threading.Thread(target=_do, daemon=True).start()
        return {
            "ok": True,
            "message": "System 2 second mein restart ho raha hai. (Restarting in 2 s)",
        }

    # ── Volume controls ─────────────────────────────────────────────────────

    def _volume_up(self):
        if SYSTEM == "Windows":
            # Press VK_VOLUME_UP twice (~+20 %)
            _press_media_key(_VK_VOLUME_UP)
            _press_media_key(_VK_VOLUME_UP)
            return {"ok": True, "message": "Volume badh gaya. (Volume increased)"}
        if SYSTEM == "Linux":
            _spawn("amixer sset Master 10%+")
            return {"ok": True, "message": "Volume badh gaya. (Volume increased)"}
        return {"ok": False, "message": "Volume control not supported on this OS."}

    def _volume_down(self):
        if SYSTEM == "Windows":
            _press_media_key(_VK_VOLUME_DOWN)
            _press_media_key(_VK_VOLUME_DOWN)
            return {"ok": True, "message": "Volume kam ho gaya. (Volume decreased)"}
        if SYSTEM == "Linux":
            _spawn("amixer sset Master 10%-")
            return {"ok": True, "message": "Volume kam ho gaya. (Volume decreased)"}
        return {"ok": False, "message": "Volume control not supported on this OS."}

    def _volume_mute(self):
        if SYSTEM == "Windows":
            _press_media_key(_VK_VOLUME_MUTE)
            return {"ok": True, "message": "Volume mute/unmute ho gaya."}
        if SYSTEM == "Linux":
            _spawn("amixer sset Master toggle")
            return {"ok": True, "message": "Volume mute/unmute ho gaya."}
        return {"ok": False, "message": "Volume mute not supported on this OS."}

    # ── Web search ──────────────────────────────────────────────────────────

    @staticmethod
    def _web_search(query: str) -> dict:
        if not query:
            return {"ok": False, "message": "Search query not provided."}
        url = "https://www.google.com/search?q=" + query.replace(" ", "+")
        webbrowser.open_new_tab(url)
        return {
            "ok": True,
            "message": f"Google search khola: '{query}'. (Opening search for '{query}')",
        }
