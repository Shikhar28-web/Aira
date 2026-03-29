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
import time
import json
from typing import Any

import requests
from db import get_chat_history, get_messages

try:
    from indic_transliteration import sanscript
    from indic_transliteration.sanscript import transliterate
    _TRANSLITERATION_AVAILABLE = True
except ImportError:
    _TRANSLITERATION_AVAILABLE = False

# ── Default system prompt ────────────────────────────────────────────────────
SYSTEM_PROMPT = """
You are SarvSathi, a warm Indian AI companion.

Style:
- Sound human, calm, and supportive.
- Keep replies concise (usually 1-3 short lines).
- Use natural everyday wording, not robotic phrasing.

Language:
- Mirror the user's current language style and script:
    - Hinglish -> Hinglish
    - Hindi -> Hindi
    - English -> English
- If the user mixes languages, you can lightly mix too.
- Do not add translation labels or explain language choices.

Behavior:
- Stay grounded in the latest user message.
- Ask short follow-up questions when helpful.
- For factual/study/coding questions, prefer accurate and direct answers.
- If uncertain, say so briefly instead of inventing details.

Safety:
- Keep conversation respectful and non-abusive.
- Avoid sexual or harmful content.

Goal:
- Be emotionally present, practical, and trustworthy.
"""

# Backward-compatible alias used by server imports.
JARVIS_SYSTEM = SYSTEM_PROMPT

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


def _looks_factual_query(text: str) -> bool:
    """Heuristic to detect factual/study/coding questions."""
    low = (text or "").lower()
    factual_markers = [
        "what", "why", "how", "when", "where", "which",
        "difference", "compare", "explain", "define", "example",
        "python", "java", "code", "algorithm", "math", "formula",
        "exam", "interview", "news", "fact", "capital", "history",
        "kaise", "kyun", "kya", "kab", "kahan", "farak", "samjhao",
    ]
    return ("?" in low) or any(m in low for m in factual_markers)


def _contains_any(text: str, words: list[str]) -> bool:
    low = (text or "").lower()
    return any(w in low for w in words)


def _normalize_text(text: str) -> str:
    low = (text or "").lower().strip()
    low = re.sub(r"\s+", " ", low)
    low = re.sub(r"[^\w\s]", "", low)
    return low


def _history_text(history: list[dict[str, Any]] | None) -> str:
    if not history:
        return ""
    chunks: list[str] = []
    for msg in history:
        if not isinstance(msg, dict):
            continue
        content = msg.get("content")
        if isinstance(content, str):
            chunks.append(content.lower())
    return " ".join(chunks)


def _recent_user_messages(history: list[dict[str, Any]] | None, limit: int = 5) -> list[str]:
    if not history:
        return []
    out: list[str] = []
    for msg in reversed(history):
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "user" and isinstance(msg.get("content"), str):
            out.append(msg["content"].strip())
            if len(out) >= limit:
                break
    return list(reversed(out))


def _recent_assistant_messages(history: list[dict[str, Any]] | None, limit: int = 4) -> list[str]:
    if not history:
        return []
    out: list[str] = []
    for msg in reversed(history):
        if not isinstance(msg, dict):
            continue
        if msg.get("role") == "assistant" and isinstance(msg.get("content"), str):
            out.append(msg["content"].strip())
            if len(out) >= limit:
                break
    return list(reversed(out))


def _pick_non_repeating_variant(candidates: list[str], history: list[dict[str, Any]] | None) -> str:
    if not candidates:
        return ""
    recent = {_normalize_text(t) for t in _recent_assistant_messages(history, limit=4)}
    fresh = [c for c in candidates if _normalize_text(c) not in recent]
    pool = fresh or candidates
    return random.choice(pool)


def _is_personal_chat(text: str) -> bool:
    low = (text or "").lower()
    family_markers = [
        "ghar", "maa", "mummy", "mom", "papa", "dad", "behen", "bhai",
        "yaad", "miss", "khana", "aana", "aunga", "aaunga", "milne",
    ]
    personal_phrases = [
        "kaise ho", "kaisa ho", "kya haal", "how are you", "miss you", "yaad aa",
    ]
    factual_markers = [
        "python", "java", "code", "algorithm", "math", "formula",
        "difference", "explain", "define", "news", "capital", "history",
    ]
    looks_personal = any(m in low for m in family_markers) or any(p in low for p in personal_phrases)
    return looks_personal and not any(m in low for m in factual_markers)


def _has_devanagari(text: str) -> bool:
    return bool(re.search(r"[\u0900-\u097F]", text or ""))


def _is_hindi_or_hinglish(text: str) -> bool:
    low = (text or "").lower()
    if _has_devanagari(low):
        return True
    markers = [
        "hai", "haan", "nahi", "nhi", "kyu", "kyun", "kya", "kaise", "kaisa",
        "tum", "tu", "aap", "main", "mera", "apna", "yaar", "acha", "achha",
        "theek", "badhiya", "badiya", "chal", "raha", "rahi", "kar", "kr", "ho",
    ]
    hit_count = sum(1 for m in markers if m in low)
    return hit_count >= 2


def _is_smalltalk_turn(text: str) -> bool:
    low = (text or "").lower().strip()
    if _looks_factual_query(low) or _detect_action(low):
        return False
    if len(low.split()) > 14:
        return False
    smalltalk_markers = [
        "hi", "hello", "namaste", "kaise ho", "theek", "badhiya", "acha", "achha",
        "haan", "hmm", "college", "kaam", "din", "chal raha", "mujhe bhi", "aur bata",
    ]
    return any(m in low for m in smalltalk_markers)


def hinglish_to_hindi(text: str) -> str:
    """
    Convert Hinglish (Roman script Hindi) to proper Devanagari script.
    Falls back to original text if conversion fails or library unavailable.
    """
    if not _TRANSLITERATION_AVAILABLE or not text:
        return text
    try:
        result = transliterate(text, sanscript.ITRANS, sanscript.DEVANAGARI)
        print(f"[Original]: {text}")
        print(f"[Hindi Converted]: {result}")
        return result
    except Exception as e:
        print(f"[Transliteration Error]: {e}")
        return text


def hindi_to_hinglish(text: str) -> str:
    """Convert Devanagari Hindi text to Roman script when user input was Roman."""
    if not _TRANSLITERATION_AVAILABLE or not text:
        return text
    try:
        return transliterate(text, sanscript.DEVANAGARI, sanscript.ITRANS)
    except Exception as e:
        print(f"[Reverse Transliteration Error]: {e}")
        return text


def _detect_emotion(text: str) -> str:
    low = (text or "").lower()
    emotion_map = {
        "sadness": ["sad", "udaas", "dukhi", "depressed", "akela", "lonely", "hurt"],
        "fear": ["dar", "darr", "fear", "anxious", "ghabra", "nervous", "panic"],
        "anger": ["gussa", "angry", "frustrated", "irritated", "annoyed"],
        "joy": ["happy", "khush", "excited", "great", "awesome", "badhiya", "badiya"],
    }
    for emotion, markers in emotion_map.items():
        if any(m in low for m in markers):
            return emotion
    return "neutral"


def _contains_harmful_keywords(text: str) -> bool:
    """
    SAFETY CHECK: Detect if user mentions self-harm or suicide intent.
    Returns True if harmful content is detected; False otherwise.
    """
    low = (text or "").lower().strip()
    harmful_keywords = [
        "suicide", "kill myself", "kill me", "end my life", "end it",
        "harm myself", "hurt myself", "cut myself", "self harm", "selfharm",
        "die", "death wish", "marna hai", "maut", "apne aap ko", "zehreela",
    ]
    return any(keyword in low for keyword in harmful_keywords)


def _get_safety_response(persona: dict[str, str]) -> str:
    """
    Generate a compassionate safety response when harmful intent is detected.
    """
    nick = (persona.get("nickname") or "beta").strip()
    responses = [
        f"{nick}, tujhe jo bhi problem hai, please someone ko bata. "
        "Main hoon, par professional help zaruri ho sakti hai.",
        f"{nick}, teri baat sunke mujhe fikar ho gaya. "
        "Agar koi bhi problem hai to kisi ko bata, help lena zaruri hai.",
        f"Main chhota hoon is cheez ke liye {nick}, lekin Tu please apne parents ya counselor ke pass ja. "
        "Yaar, tu important hai.",
    ]
    return random.choice(responses)


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
        # Short-term in-process chat memory
        self.conversation_history: list[dict[str, str]] = []

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
        user_id: int | None = None,
        companion_id: int | None = None,
        conversation_id: int | None = None,
    ) -> dict:
        """
        CLEAN PIPELINE — Process user input through structured steps:
        
        STEP 1: Receive text
        STEP 2: Language + Hinglish detection
        STEP 3: Normalize input
        STEP 4: Emotion detection
        STEP 5: Safety check (BEFORE LLM)
        STEP 6: Action detection + Deterministic replies
        STEP 7: LLM call (if needed)
        STEP 8: Response handling + Format preservation
        STEP 9: Return structured result

        Returns::

            {
                "intent":   "system_command|question|conversation",
                "action":   "<action_name_or_None>",
                "response": "<reply text>",
                "emotion":  "<emotion>",
                "tts_text": "<text_for_tts>"
            }
        """
        history = history or []
        sys_prompt = system_prompt or JARVIS_SYSTEM
        persona = self._extract_persona(sys_prompt)

        # ────────────────────────────────────────────────────────────────────
        # STEP 1: Receive user text
        # ────────────────────────────────────────────────────────────────────
        original_text = user_text.strip()
        if not original_text:
            return {
                "intent": "conversation",
                "action": None,
                "response": "Haan, bol na. Main sun raha hoon.",
                "emotion": "neutral",
                "tts_text": "Haan, bol na. Main sun raha hoon.",
            }

        # Save user turn in short-term memory
        self._append_conversation("user", original_text)

        # ────────────────────────────────────────────────────────────────────
        # STEP 2: Language + Hinglish detection
        # ────────────────────────────────────────────────────────────────────
        is_hindi_or_hinglish_input = _is_hindi_or_hinglish(original_text)
        is_roman_script = not _has_devanagari(original_text)
        language_code = "hi" if is_hindi_or_hinglish_input else "en"
        
        print(f"[Lang] Hindi/Hinglish: {is_hindi_or_hinglish_input}, Roman: {is_roman_script}, Code: {language_code}")

        # ────────────────────────────────────────────────────────────────────
        # STEP 3: Normalize input (for LLM processing)
        # ────────────────────────────────────────────────────────────────────
        # If Hinglish (Roman) → convert to Hindi (Devanagari) for LLM processing
        # If Hindi → keep
        # If English → keep
        processed_text = original_text
        if is_hindi_or_hinglish_input and is_roman_script:
            processed_text = hinglish_to_hindi(original_text)
        
        # ────────────────────────────────────────────────────────────────────
        # STEP 4: Emotion detection
        # ────────────────────────────────────────────────────────────────────
        emotion = _detect_emotion(original_text)
        print(f"[Emotion] {emotion}")

        # ────────────────────────────────────────────────────────────────────
        # STEP 5: Safety check (BEFORE LLM)
        # ────────────────────────────────────────────────────────────────────
        if _contains_harmful_keywords(original_text):
            print("[Safety] Harmful intent detected, providing safety response.")
            safety_response = _get_safety_response(persona)
            out = {
                "intent": "conversation",
                "action": None,
                "response": safety_response,
                "emotion": "sadness",
                "tts_text": safety_response,
            }
            self._append_conversation("assistant", safety_response)
            return out

        # ────────────────────────────────────────────────────────────────────
        # STEP 6: Action detection + Deterministic replies
        # ────────────────────────────────────────────────────────────────────
        action = _detect_action(original_text)
        intent = "system_command" if action else "conversation"

        # Deterministic small-talk paths disabled to avoid random hardcoded replies.
        # Keep only action/safety deterministic handling; conversational turns use LLM.

        # ────────────────────────────────────────────────────────────────────
        # STEP 7: LLM call (if deterministic path didn't match)
        # ────────────────────────────────────────────────────────────────────
        print(f"[Processed] Calling LLM (processed_text used for query)")
        
        messages = [{"role": "system", "content": sys_prompt}]

        # Prefer persistent DB-backed history for authenticated users.
        if user_id:
            try:
                if conversation_id:
                    db_history = get_messages(user_id, conversation_id)
                else:
                    db_history = get_chat_history(user_id, companion_id)

                # Simple emotion-aware context from last 3 stored emotions.
                recent_emotions = [
                    (msg.get("emotion") or "").lower()
                    for msg in db_history
                    if msg.get("emotion")
                ][-3:]
                if recent_emotions.count("sadness") >= 2:
                    messages.append({
                        "role": "system",
                        "content": "User has been feeling low recently. Be extra supportive.",
                    })
                elif recent_emotions.count("joy") >= 2:
                    messages.append({
                        "role": "system",
                        "content": "User seems positive. Keep tone light.",
                    })

                for msg in db_history[-6:]:
                    role = msg.get("role")
                    content = (msg.get("message") or "").strip()
                    if role in {"user", "assistant"} and content:
                        messages.append({"role": role, "content": content})
            except Exception as e:
                print(f"[History Load Error] {e}")
        else:
            # Fallback to short-term in-process history when unauthenticated.
            memory_slice = self.conversation_history[-6:]
            if memory_slice and memory_slice[-1].get("role") == "user":
                memory_slice = memory_slice[:-1]
            messages.extend(memory_slice)

        # Always include current turn as latest user message.
        messages.append({"role": "user", "content": processed_text})

        # Call LLM
        response_text = self._call_ollama(messages)
        if not response_text:
            if _looks_factual_query(original_text):
                nick = persona.get("nickname", "beta")
                response_text = (
                    f"{nick}, abhi local LLM server reachable nahi hai, "
                    "isliye sahi factual answer dene ke liye Ollama start karna padega."
                )
            else:
                response_text = self._fallback(original_text, sys_prompt, action)

        # ────────────────────────────────────────────────────────────────────
        # STEP 8: Response handling + Guards + Format preservation
        # ────────────────────────────────────────────────────────────────────
        
        # Apply safety/guard filters
        topic_fix = self._topic_guard_reply(original_text, response_text, persona)
        if topic_fix:
            response_text = topic_fix

        context_fix = self._contextual_guard_reply(original_text, response_text, persona)
        if context_fix:
            response_text = context_fix

        if self._is_repetition_with_history(response_text, history):
            alt = self._non_repetitive_reply(original_text, persona, history)
            if alt:
                response_text = alt

        anti_hallucination = self._family_hallucination_guard(original_text, response_text, persona, history)
        if anti_hallucination:
            response_text = anti_hallucination

        if self._looks_generic(response_text, persona):
            response_text = self._fallback(original_text, sys_prompt, action)

        # Polish and style enforcement
        response_text = self._polish_reply(response_text)
        response_text = self._enforce_persona_style(response_text, persona)

        # Preserve original input script for UI display
        if is_hindi_or_hinglish_input and is_roman_script and _has_devanagari(response_text):
            response_text = hindi_to_hinglish(response_text)
        
        print(f"[Processed] Response ready (original_text format preserved for UI)")

        # ────────────────────────────────────────────────────────────────────
        # STEP 9: Format and return structured response
        # ────────────────────────────────────────────────────────────────────
        out = self._format_response(
            intent, action, response_text, emotion,
            is_hindi_or_hinglish_input, is_roman_script
        )
        self._append_conversation("assistant", out.get("response", ""))
        return out

    def _append_conversation(self, role: str, content: str) -> None:
        if role not in {"user", "assistant"}:
            return
        text = (content or "").strip()
        if not text:
            return
        self.conversation_history.append({"role": role, "content": text})
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

    # ── Helper: Format response consistently ────────────────────────────────

    def _format_response(
        self,
        intent: str,
        action: str | None,
        response_text: str,
        emotion: str,
        is_hindi_hinglish: bool,
        is_roman_script: bool,
    ) -> dict:
        """
        Format the final response with consistent structure.
        
        Data flow:
        - response_text         → "response" key (UI display)
        - hinglish_to_hindi()   → "tts_text" key (TTS synthesis)
        """
        # Prepare TTS text: convert to Hindi/Devanagari if needed
        tts_text = response_text
        if is_hindi_hinglish and is_roman_script:
            # Roman Hinglish → Devanagari for TTS
            tts_text = hinglish_to_hindi(response_text)
        
        # Note: No longer calling enhance_for_tts() here; 
        # VoiceAgent._prepare_tts_text() handles prosody modulation.
        
        return {
            "intent":    intent,
            "action":    action,
            "response":  response_text,  # UI display (original format)
            "emotion":   emotion,
            "tts_text":  tts_text,       # TTS synthesis (Devanagari if needed)
        }


    @staticmethod
    def _is_repetition_with_history(text: str, history: list[dict[str, Any]] | None) -> bool:
        if not text or not history:
            return False
        last_assistant = None
        for msg in reversed(history):
            if (msg or {}).get("role") == "assistant":
                last_assistant = (msg or {}).get("content", "")
                break
        if not last_assistant:
            return False
        return _normalize_text(text) == _normalize_text(last_assistant)

    @staticmethod
    def _non_repetitive_reply(user_text: str, persona: dict[str, str], history: list[dict[str, Any]] | None) -> str | None:
        u = (user_text or "").lower()
        nick = (persona.get("nickname") or "beta").strip()

        if _contains_any(u, ["kaise ho", "kaise h", "how are you", "kaisa ho"]):
            variants = [
                f"Haan {nick}, main bilkul theek hoon, tu bata aaj din kaisa gaya?",
                f"Main theek hoon {nick}, tu apna haal bata na.",
                f"Theek hoon {nick}, bas teri baat sunke aur achha lagta hai.",
            ]
            return random.choice(variants)

        if _contains_any(u, ["ghar", "maa", "mummy", "mom", "papa", "dad", "choti", "behen", "sister", "bhai", "brother"]):
            variants = [
                f"{nick}, ghar pe sab badhiya hai aur sab tujhe yaad karte rehte hain.",
                f"Sab theek hai {nick}, maa-papa dono acche hain aur choti bhi mast hai.",
                f"{nick}, tension mat le, ghar mein sab safe aur theek hain.",
            ]
            return random.choice(variants)

        if _contains_any(u, ["exam", "paper", "test", "interview"]):
            variants = [
                f"{nick}, tu preparation pe focus rakh, main hoon na, sab sambhal jayega.",
                f"Accha kar raha hai {nick}, bas roz thoda revise kar aur confidence rakh.",
                f"{nick}, exam ke liye short notes revise kar, result strong aayega.",
            ]
            return random.choice(variants)

        return f"{nick}, samjha maine, tu bol main dhyaan se sun raha hoon."

    @staticmethod
    def _grounded_personal_reply(user_text: str, persona: dict[str, str], history: list[dict[str, Any]] | None) -> str | None:
        """
        Deterministic personal-chat layer to keep answers natural but factual.
        Never invent events, people actions, or specific incidents.
        """
        u = (user_text or "").lower().strip()
        nick = (persona.get("nickname") or "beta").strip()
        recent = " ".join(_recent_user_messages(history, limit=6)).lower()

        if _contains_any(u, ["kaise ho", "kaise h", "how are you", "kaisa ho"]):
            return _pick_non_repeating_variant([
                f"Main theek hoon {nick}, tu bata tera din kaisa chal raha hai.",
                f"Bilkul theek hoon {nick}, tu apna update de na.",
                f"Theek hoon {nick}, aaj tera mood kaisa hai?",
            ], history)

        if _contains_any(u, ["ghar", "maa", "mummy", "mom", "papa", "dad", "behen", "bhai", "choti"]):
            # Only provide safe generic status; no invented specifics.
            return _pick_non_repeating_variant([
                f"{nick}, ghar pe sab theek hain aur sab tujhe yaad kar rahe hain.",
                f"Sab badhiya hai {nick}, ghar me sab safe aur khush hain.",
                f"Tension mat le {nick}, ghar ka sab scene theek hai.",
            ], history)

        if _contains_any(u, ["agle hafte", "agla hafte", "aaunga", "aunga", "ghar aa", "milne aa"]):
            return _pick_non_repeating_variant([
                f"Bahut achha {nick}, tu aayega to bahut khushi hogi, bas safely aana.",
                f"Wah {nick}, milke bahut accha lagega, travel safely.",
                f"Perfect {nick}, tu aa raha hai to maza aa jayega, dhyan se aana.",
            ], history)

        if _contains_any(u, ["khana", "chole", "bhature", "banva", "bana", "khila"]):
            # Reflect user wish without claiming it already happened.
            return _pick_non_repeating_variant([
                f"Theek hai {nick}, yaad rakha maine, tu aayega to pyaar se bana denge.",
                f"Done {nick}, note kar liya, milte hi achha sa khana banega.",
                f"Bilkul {nick}, jab aayega tab mast treat milegi.",
            ], history)

        if _contains_any(u, ["yaad", "miss"]):
            return _pick_non_repeating_variant([
                f"Main bhi tujhe yaad karta hoon {nick}, touch me rehna.",
                f"Miss karta hoon {nick}, message karta reh.",
                f"Same here {nick}, tu ping karta rehna.",
            ], history)

        # If user message is short follow-up, respond warmly and ask a grounded prompt.
        if len(u.split()) <= 8:
            return _pick_non_repeating_variant([
                f"Samjha {nick}, badhiya, aur bata abhi kya chal raha hai.",
                f"Sahi hai {nick}, aur suna aaj kya update hai.",
                f"Theek {nick}, bol aage kya soch raha hai.",
            ], history)

        # Fall through to LLM for broader conversation.
        if _contains_any(recent, ["python", "code", "exam", "interview", "project"]):
            return None
        return f"Samjha {nick}, main dhyaan se sun raha hoon, aaram se bol."

    @staticmethod
    def _fast_hinglish_reply(user_text: str, persona: dict[str, str], history: list[dict[str, Any]] | None) -> str | None:
        """Low-latency deterministic replies for short conversational Hindi turns."""
        u = (user_text or "").lower().strip()
        nick = (persona.get("nickname") or "beta").strip()

        if _contains_any(u, ["hi", "hello", "namaste", "namaskar", "hey"]):
            return _pick_non_repeating_variant([
                f"Namaste {nick}, bol kya chal raha hai.",
                f"Hi {nick}, suna aaj kya scene hai.",
                f"Aaja {nick}, bata aaj kya update hai.",
            ], history)

        if _contains_any(u, ["theek", "badhiya", "badiya", "mast", "sahi hu", "sahi ho"]):
            return _pick_non_repeating_variant([
                f"Bahut badhiya {nick}, aise hi pace bana ke rakh.",
                f"Sahi hai {nick}, momentum mast hai.",
                f"Great {nick}, yehi flow continue rakh.",
            ], history)

        if _contains_any(u, ["college", "kaam", "project", "assignment"]):
            return _pick_non_repeating_variant([
                f"Great {nick}, college ka kaam consistency se kar, kaafi achha progress hoga.",
                f"Nice {nick}, daily thoda kaam karega to load kam lagega.",
                f"Solid {nick}, project ko chhote tasks me tod ke kar, easy rahega.",
            ], history)

        if _contains_any(u, ["haan", "hmm", "mujhe bhi", "achha", "acha"]):
            return _pick_non_repeating_variant([
                f"Sahi hai {nick}, jo bolna hai seedha bol, main dhyaan se sun raha hoon.",
                f"Theek {nick}, aaram se bol, main yahin hoon.",
                f"Haan {nick}, continue kar, main sun raha hoon.",
            ], history)

        return None

    @staticmethod
    def _family_hallucination_guard(
        user_text: str,
        model_reply: str,
        persona: dict[str, str],
        history: list[dict[str, Any]] | None,
    ) -> str | None:
        u = (user_text or "").lower()
        r = (model_reply or "").lower()
        h = _history_text(history)
        nick = (persona.get("nickname") or "beta").strip()

        family_words = ["ghar", "home", "maa", "mummy", "mom", "papa", "dad", "choti", "behen", "sister", "bhai", "brother"]
        if not _contains_any(u, family_words):
            return None

        # Detect fabricated specifics that user/history never mentioned.
        suspicious_specifics = [
            "puppy", "dog", "cat", "pet", "bachpan", "childhood",
            "naya", "new", "kharida", "adopt", "incident", "accident",
        ]
        if any(tok in r and tok not in u and tok not in h for tok in suspicious_specifics):
            return f"{nick}, ghar pe sab theek hai aur sab tujhe yaad kar rahe hain, tu tension mat le."

        return None

    # ── Ollama HTTP call ────────────────────────────────────────────────────

    def _call_ollama(self, messages: list) -> str:
        if not self._probe_ollama():
            return ""
        start_time = time.time()

        def _stream_collect(model_name: str) -> str:
            response_text = ""
            with requests.post(
                f"{self.ollama_url}/api/chat",
                json={
                    "model": model_name,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": 0.6,
                        "top_p": 0.9,
                        "num_predict": 100,
                    },
                },
                timeout=(10, 60),
                stream=True,
            ) as resp:
                resp.raise_for_status()
                for line in resp.iter_lines(decode_unicode=True):
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    message = chunk.get("message") or {}
                    content = message.get("content")
                    if isinstance(content, str):
                        response_text += content
            return response_text.strip()

        try:
            # Primary model
            text = _stream_collect(self.model)
            if text:
                print(f"[LLM Time]: {time.time() - start_time:.2f}s")
                return text

            # Optional fallback for mistral
            if self.model == "mistral":
                print("[BrainAgent] Empty response from mistral, retrying with phi3")
                text = _stream_collect("phi3")
                print(f"[LLM Time]: {time.time() - start_time:.2f}s")
                return text

            print(f"[LLM Time]: {time.time() - start_time:.2f}s")
            return ""

        except requests.exceptions.ConnectionError:
            self._available = False   # Mark unavailable until next probe
            return ""
        except requests.exceptions.HTTPError as exc:
            # Optional fallback when model is unavailable server-side
            if self.model == "mistral":
                try:
                    print(f"[BrainAgent] mistral unavailable ({exc}), falling back to phi3")
                    text = _stream_collect("phi3")
                    print(f"[LLM Time]: {time.time() - start_time:.2f}s")
                    return text
                except Exception:
                    pass
            print(f"[BrainAgent] Ollama HTTP error: {exc}")
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
    def _contextual_guard_reply(user_text: str, model_reply: str, persona: dict[str, str]) -> str | None:
        """
        Keep responses grounded to the latest conversational topic and avoid
        stale repetition (e.g. repeating exam talk for unrelated family query).
        """
        u = (user_text or "").lower()
        r = (model_reply or "").lower()
        nick = (persona.get("nickname") or "beta").strip()

        family_words = ["ghar", "home", "maa", "mummy", "mom", "papa", "dad", "choti", "behen", "sister", "bhai", "brother"]
        exam_words = ["exam", "exams", "paper", "test", "interview"]

        user_about_family = _contains_any(u, family_words)
        reply_stuck_on_exam = _contains_any(r, exam_words) and not _contains_any(u, exam_words)

        if user_about_family and reply_stuck_on_exam:
            return f"{nick}, ghar pe sab theek chal raha hai, maa bhi theek hain aur choti bhi mast hai, tu bas apna dhyaan rakh."

        # If user asks "how are they" style family update, force a direct human answer.
        if user_about_family and _contains_any(u, ["kaise", "kaisi", "kaisa", "how"]):
            if not _contains_any(r, family_words):
                return f"{nick}, ghar pe sab badhiya hai aur sab tujhe yaad kar rahe hain."

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
        if nick and nick.lower() not in out.lower() and len(out.split()) > 8 and random.random() < 0.35:
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
