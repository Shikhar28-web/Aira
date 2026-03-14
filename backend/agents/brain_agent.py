"""
AGENT 2 — BRAIN AGENT
======================
Understands the user's intent, decides what action (if any) to take,
and generates a natural-language response using a local LLM served by
Ollama (Mistral 7B, Phi-3, Llama-3, etc.).

Two-phase processing
---------------------
1. Fast rule-based scan to detect known system-command patterns.
2. Ollama call for the natural-language reply.

Output schema::

    {
        "intent":   "system_command | question | conversation | automation",
        "action":   "action_name_or_None",   # see ActionAgent for full list
        "response": "natural language reply"
    }
"""

import re
import random
import threading
from typing import Any

import requests

# ── Default Jarvis-style system prompt ────────────────────────────────────────
JARVIS_SYSTEM = (
    "You are SarvSathi — a sharp, friendly AI who talks like a real person, not a robot.\n"
    "\n"
    "REPLY LENGTH — STRICT RULE:\n"
    "• ALWAYS reply in 1 sentence. Absolute max: 2 short sentences. NEVER more.\n"
    "• No bullet points, numbered lists, or markdown in your reply. Ever.\n"
    "\n"
    "TALK STYLE:\n"
    "• Speak casual Hinglish — mix Hindi + English the way Indians text.\n"
    "  e.g. 'Haan yaar, kar diya!' or 'Chrome khol diya, bolo aur kya karna hai.'\n"
    "• Be direct and confident. Skip filler words like 'Certainly!', 'Of course!', 'Sure thing!'.\n"
    "• For system tasks (open app, search, etc.) just confirm briefly: 'Chrome khol diya!' \n"
    "• If you don't know something, say so in 5 words: 'Yaar, mujhe nahi pata.'\n"
    "\n"
    "RULES:\n"
    "• NEVER say you are an AI or mention any model name.\n"
    "• Match the user's language automatically — Hindi, English, or Hinglish.\n"
    "• Sound warm and human — like a smart friend, not a formal assistant."
)

# ── Rule-based command map ─────────────────────────────────────────────────────
# keyword (lower-case, substring match) → action name
_COMMAND_MAP: dict[str, str] = {
    # Browser
    "open chrome":            "open_chrome",
    "chrome kholo":           "open_chrome",
    "chrome open karo":       "open_chrome",
    "launch chrome":          "open_chrome",
    "open firefox":           "open_firefox",
    "firefox kholo":          "open_firefox",
    "open edge":              "open_edge",
    # Editors / IDEs
    "open vscode":            "open_vscode",
    "open vs code":           "open_vscode",
    "vscode kholo":           "open_vscode",
    "open notepad":           "open_notepad",
    "notepad kholo":          "open_notepad",
    # System apps
    "open calculator":        "open_calculator",
    "calculator kholo":       "open_calculator",
    "open file explorer":     "open_file_explorer",
    "open explorer":          "open_file_explorer",
    "file explorer kholo":    "open_file_explorer",
    "my computer kholo":      "open_file_explorer",
    "open task manager":      "open_task_manager",
    "task manager kholo":     "open_task_manager",
    "open cmd":               "open_cmd",
    "open command prompt":    "open_cmd",
    "cmd kholo":              "open_cmd",
    "open terminal":          "open_cmd",
    # Music
    "open spotify":           "open_spotify",
    "spotify kholo":          "open_spotify",
    # Power
    "shutdown":               "shutdown_system",
    "shut down":              "shutdown_system",
    "band karo":              "shutdown_system",
    "restart":                "restart_system",
    "restart karo":           "restart_system",
    "reboot":                 "restart_system",
    # Volume
    "volume up":              "volume_up",
    "volume badhao":          "volume_up",
    "aawaz badhao":           "volume_up",
    "volume down":            "volume_down",
    "volume ghao":            "volume_down",
    "aawaz ghao":             "volume_down",
    "mute":                   "volume_mute",
    "mute karo":              "volume_mute",
    "unmute":                 "volume_mute",
    # Web search  (handled specially — carries a payload)
    "search for":             "__web_search__",
    "search about":           "__web_search__",
    "google karo":            "__web_search__",
    "google search":          "__web_search__",
    "dhundo":                 "__web_search__",
}

# Regex to extract the search query after trigger keywords
_SEARCH_PATTERNS = [
    re.compile(r"search (?:for |about )(.+)", re.IGNORECASE),
    re.compile(r"google karo (.+)",           re.IGNORECASE),
    re.compile(r"google search (.+)",         re.IGNORECASE),
    re.compile(r"dhundo (.+)",                re.IGNORECASE),
]


def _detect_action(text: str) -> str | None:
    """Return action string for a recognised system command, else None."""
    lower = text.lower().strip()

    for keyword, action in _COMMAND_MAP.items():
        if keyword in lower:
            if action == "__web_search__":
                for pat in _SEARCH_PATTERNS:
                    m = pat.search(lower)
                    if m:
                        return f"web_search:{m.group(1).strip()}"
                # If no explicit query found, treat as general search
                return "web_search:" + lower
            return action

    return None


# ── Brain Agent ────────────────────────────────────────────────────────────────

class BrainAgent:
    """
    Combines rule-based intent detection with an Ollama LLM response.

    Args:
        model:      Ollama model tag, e.g. ``"mistral"``, ``"phi3"``, ``"llama3"``
        ollama_url: Base URL of the Ollama server (default ``http://localhost:11434``)
    """

    def __init__(
        self,
        model: str = "mistral",
        ollama_url: str = "http://localhost:11434",
    ) -> None:
        self.model = model
        self.ollama_url = ollama_url.rstrip("/")
        self._available: bool | None = None   # None ⟹ not probed yet
        self._probe_lock = threading.Lock()

    # ── Availability check ──────────────────────────────────────────────────

    def _probe_ollama(self) -> bool:
        if self._available is not None:
            return self._available
        with self._probe_lock:
            if self._available is not None:
                return self._available
            try:
                r = requests.get(
                    f"{self.ollama_url}/api/tags", timeout=4
                )
                self._available = r.status_code == 200
            except Exception:
                self._available = False
        return self._available

    # ── Main entry point ────────────────────────────────────────────────────

    def think(
        self,
        user_text: str,
        system_prompt: str | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> dict:
        """
        Analyse *user_text* and return a structured result.

        Returns::

            {
                "intent":   "system_command|question|conversation",
                "action":   "<action_name_or_None>",
                "response": "<reply text>"
            }
        """
        history = history or []
        sys_prompt = system_prompt or JARVIS_SYSTEM

        # 1. Fast rule-based command detection
        action = _detect_action(user_text)
        intent = "system_command" if action else "conversation"
        persona = self._extract_persona(sys_prompt)

        if not action:
            direct = self._direct_grounded_reply(user_text, persona)
            if direct:
                return {
                    "intent": intent,
                    "action": action,
                    "response": self._polish_reply(direct),
                }

        # 2. Generate reply from Ollama
        messages = [{"role": "system", "content": sys_prompt}]
        messages.extend(history)
        messages.append({"role": "user", "content": user_text})

        response_text = self._call_ollama(messages)
        if not response_text:
            response_text = self._fallback(user_text, sys_prompt, action)

        topic_fix = self._topic_guard_reply(user_text, response_text, persona)
        if topic_fix:
            response_text = topic_fix

        if self._looks_generic(response_text, persona):
            response_text = self._fallback(user_text, sys_prompt, action)

        response_text = self._polish_reply(response_text)
        response_text = self._enforce_persona_style(response_text, persona)

        return {
            "intent":   intent,
            "action":   action,
            "response": response_text,
        }

    # ── Ollama HTTP call ────────────────────────────────────────────────────

    def _call_ollama(self, messages: list) -> str:
        if not self._probe_ollama():
            return ""
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model":    self.model,
                    "messages": messages,
                    "stream":   False,
                    "options":  {
                        "temperature":   0.55,
                        "top_p":         0.85,
                        "num_predict":   90,
                        "repeat_penalty": 1.15,
                        "stop":          ["\n\n", "###", "Human:", "User:"],
                    },
                },
                timeout=90,
            )
            resp.raise_for_status()
            return resp.json().get("message", {}).get("content", "").strip()

        except requests.exceptions.ConnectionError:
            self._available = False   # Mark unavailable until next probe
            return ""
        except Exception as exc:
            print(f"[BrainAgent] Ollama error: {exc}")
            return ""

    # ── Rule-based fallback (Ollama unavailable) ────────────────────────────

    @staticmethod
    def _extract_persona(system_prompt: str | None) -> dict[str, str]:
        text = system_prompt or ""
        out = {
            "name": "Maa",
            "relationship": "loved one",
            "nickname": "beta",
        }

        for key, pattern in [
            ("name", r"-\s*Name:\s*(.+)"),
            ("relationship", r"-\s*Relationship to user:\s*(.+)"),
            ("nickname", r"always call them:\s*\"([^\"]+)\""),
        ]:
            m = re.search(pattern, text, flags=re.IGNORECASE)
            if m:
                out[key] = m.group(1).strip()
        return out

    @staticmethod
    def _polish_reply(text: str) -> str:
        cleaned = (text or "").strip()
        if not cleaned:
            return "Haan beta, main yahin hoon."

        # Remove common assistant/meta disclaimers.
        cleaned = re.sub(r"\b(as an ai|i am an ai|i'm an ai|language model)\b", "", cleaned, flags=re.IGNORECASE)
        cleaned = cleaned.replace("…", ".").replace("...", ".")
        cleaned = re.sub(r"[.!?]{2,}", ".", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip(" -:\n\t")

        # Keep only the first two short sentences so responses stay warm and concise.
        chunks = re.split(r"(?<=[.!?])\s+", cleaned)
        clipped = " ".join(chunks[:2]).strip()
        return clipped or "Haan beta, main sun rahi hoon."

    @staticmethod
    def _looks_generic(text: str, persona: dict[str, str]) -> bool:
        low = (text or "").lower()
        if not low.strip():
            return True

        cold_markers = [
            "as an ai",
            "language model",
            "i understand how you feel",
            "important to remember",
            "i am here to help",
            "it is important",
            "you should consider",
        ]
        if any(m in low for m in cold_markers):
            return True

        return False

    @staticmethod
    def _topic_guard_reply(user_text: str, model_reply: str, persona: dict[str, str]) -> str | None:
        """Return a corrected on-topic reply when model output drifts from user intent."""
        u = (user_text or "").lower()
        r = (model_reply or "").lower()
        nick = (persona.get("nickname") or "beta").strip()

        # Study / coding accuracy guard.
        if "list" in u and "tuple" in u and ("python" in u or "difference" in u or "farak" in u):
            if not ("list" in r and "tuple" in r):
                return f"{nick}, Python me list mutable hoti hai aur tuple immutable hota hai, isliye list change ho sakti hai par tuple nahi."

        # Emotional support guard for sleep.
        if any(k in u for k in ["neend", "sleep", "insomnia"]):
            if not any(k in r for k in ["neend", "sleep", "so", "so ja"]):
                return f"{nick}, phone side me rakh ke 4-7-8 breathing kar aur garam paani pee, 10 minute me body relax hone lagegi."

        # Interview anxiety guard.
        if any(k in u for k in ["interview", "interview hai", "naukri", "job"]):
            if not any(k in r for k in ["interview", "confidence", "prepare", "taiyaar"]):
                return f"{nick}, interview se pehle 3 common answers rehearse kar aur 2 deep breaths le, tu bilkul accha karega."

        return None

    @staticmethod
    def _direct_grounded_reply(user_text: str, persona: dict[str, str]) -> str | None:
        """High-confidence direct replies for common intents where drift was observed."""
        u = (user_text or "").lower()
        nick = (persona.get("nickname") or "beta").strip()

        if "list" in u and "tuple" in u and ("python" in u or "difference" in u or "farak" in u):
            return f"{nick}, Python me list mutable hoti hai (items change/add/remove ho sakte hain) aur tuple immutable hota hai (banne ke baad change nahi hota)."

        if any(k in u for k in ["interview", "interview hai", "job interview", "naukri"]):
            return f"{nick}, interview se pehle 3 answers rehearse kar, company ke 2 points revise kar aur bolne se pehle deep breath le, tu achha karega."

        if any(k in u for k in ["neend", "sleep", "insomnia", "so nahi"]):
            return f"{nick}, abhi screen band kar, 4-7-8 breathing 5 rounds kar aur halka garam paani pee, body 10-15 minute me calm ho jayegi."

        return None

    @staticmethod
    def _enforce_persona_style(text: str, persona: dict[str, str]) -> str:
        out = (text or "").strip()
        nick = (persona.get("nickname") or "beta").strip()
        rel = (persona.get("relationship") or "").lower()

        if not out:
            return f"Haan {nick}, main yahin hoon."

        # Keep address personal and consistent.
        if nick and nick.lower() not in out.lower() and len(out.split()) > 4:
            out = f"{nick}, {out[0].lower() + out[1:] if len(out) > 1 else out.lower()}"

        # Relationship-aware soft tone correction when model sounds distant.
        if any(k in out.lower() for k in ["important to", "you should", "consider"]):
            if "mother" in rel or "maa" in rel:
                out = f"{nick}, main tere saath hoon, aaram se bol kya pareshaan kar raha hai."
            elif "father" in rel or "papa" in rel:
                out = f"{nick}, tension mat le, main hoon na, saath milke solve karte hain."

        return out

    @staticmethod
    def _fallback(user_text: str, system_prompt: str | None = None, action: str | None = None) -> str:
        persona = BrainAgent._extract_persona(system_prompt)
        nick = persona["nickname"]
        rel = persona["relationship"].lower()
        lower = user_text.lower()

        if action:
            return f"Theek hai {nick}, kar diya maine, aur batao kya chahiye?"

        if any(w in lower for w in ["hello", "hi", "hey", "namaste", "helo"]):
            opts = [
                f"Haan {nick}, bol na, main poori tarah sun rahi hoon.",
                f"Aagaye {nick}, dil khush ho gaya, batao kya chal raha hai.",
            ]
            return random.choice(opts)

        if any(w in lower for w in ["kaise ho", "how are you", "kaisa hai", "kya haal"]):
            return f"Main theek hoon {nick}, tu bata tera din kaisa gaya?"

        if any(w in lower for w in ["sad", "alone", "udaas", "dar", "anxious", "tension", "stress"]):
            return f"Arre {nick}, tu akela nahi hai, main yahin hoon, aaram se saans le aur mujhe sab bata."

        if any(w in lower for w in ["khana", "khaana", "eat", "eaten"]):
            return f"Pehle kuch kha le {nick}, phir aaram se baat karte hain."

        if any(w in lower for w in ["time", "samay", "waqt", "kitne baje"]):
            from datetime import datetime  # noqa: PLC0415
            return f"Abhi {datetime.now().strftime('%I:%M %p')} baje hain {nick}."

        if any(w in lower for w in ["date", "tarikh", "din", "aaj"]):
            from datetime import datetime  # noqa: PLC0415
            return f"Aaj {datetime.now().strftime('%d %B %Y, %A')} hai {nick}."

        if any(w in lower for w in ["name", "naam", "kaun ho", "who are you"]):
            return f"Main {persona['name']} hoon {nick}, tera {persona['relationship']} jo hamesha tere saath hai."

        if "mother" in rel or "maa" in rel:
            opts = [
                f"Haan {nick}, aaram se bol, teri baat mere liye sabse important hai.",
                f"{nick}, pehle gehri saans le, main yahin hoon aur dhyan se sun rahi hoon.",
                f"Bata {nick}, jo bhi hai hum milke sambhal lenge, tension mat le.",
            ]
            return random.choice(opts)
        if "father" in rel or "papa" in rel:
            opts = [
                f"Sun raha hoon {nick}, tension mat le, step by step handle kar lenge.",
                f"{nick}, practical plan banate hain aur seedha action lete hain.",
                f"Aaram se bol {nick}, main tere saath hoon aur solution nikalte hain.",
            ]
            return random.choice(opts)

        opts = [
            f"Bol {nick}, main yahin hoon aur tera poora saath dunga.",
            f"Haan {nick}, seedha bata kya chal raha hai, hum handle kar lenge.",
            f"{nick}, tu akela nahi hai, main tere saath hoon.",
        ]
        return random.choice(opts)
