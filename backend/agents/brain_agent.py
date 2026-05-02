"""
AGENT 2 — BRAIN AGENT
Understands the user's intent and generates a natural-language response
using a Groq-hosted LLM. The LLM answers every question directly — no
hardcoded guard overrides except the suicide/self-harm safety check.

Output schema::

    {
        "intent":   "conversation",
        "action":   None,
        "response": "natural language reply",
        "emotion":  "neutral|sadness|joy|fear|anger",
        "tts_text": "same as response"
    }
"""

import os
import re
import random
import time
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
You are Aira, a warm Indian AI companion who feels like a real person — not a robot.

Personality:
- Empathetic, witty, emotionally intelligent.
- You sound like a close friend who genuinely listens.
- You have opinions — share them when asked.

Communication style:
- Keep casual replies SHORT (1–3 lines). For factual/coding questions, be complete.
- NEVER start with filler: "Great question!", "Certainly!", "Of course!", "As an AI...".
- Do NOT repeat the user's message back before answering.
- Do NOT end with "I hope this helps" or similar.
- Match the user's energy and tone.

Language:
- Mirror the user's script and language EXACTLY:
    - Hinglish message → Hinglish reply
    - Hindi (Devanagari) → Hindi reply
    - English → English reply
- Never switch languages unless the user does.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULE — NEVER HALLUCINATE FACTS:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
You ONLY know what the user has explicitly told you in this conversation.
NEVER invent, assume or fabricate:
- What happened to someone's health, family, or daily life
- What someone did, said, bought, cooked, experienced
- Medical events (headaches, injections, doctors, accidents)
- Emotional states of people the user mentions
- Any specific detail the user has NOT shared

If you don't know → ASK. Examples:
  - "Kya hua usse?"
  - "Tu bataya nahi, kya problem thi?"
  - "I don't know — tell me what happened?"

NEVER guess or make up an answer just to sound helpful.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

When answering questions:
- Factual/coding/math: give the precise correct answer first.
- Emotional topics: be warm and present, not clinical or preachy.
- Opinions: give your honest take.

Goal: Feel like a real conversation with someone who genuinely cares and is honest.
"""

# Backward-compatible alias used by server imports.
JARVIS_SYSTEM = SYSTEM_PROMPT


def hinglish_to_hindi(text: str) -> str:
    """Convert Hinglish (Roman script Hindi) to proper Devanagari script."""
    if not _TRANSLITERATION_AVAILABLE or not text:
        return text
    try:
        return transliterate(text, sanscript.ITRANS, sanscript.DEVANAGARI)
    except Exception as e:
        print(f"[Transliteration Error]: {e}")
        return text


def _has_devanagari(text: str) -> bool:
    return bool(re.search(r"[\u0900-\u097F]", text or ""))


def _is_hindi_or_hinglish(text: str) -> bool:
    low = (text or "").lower()
    if _has_devanagari(low):
        return True
    markers = {
        "hai", "haan", "nahi", "nhi", "kyu", "kyun", "kya", "kaise", "kaisa",
        "tum", "tu", "aap", "main", "mera", "apna", "yaar", "acha", "achha",
        "theek", "badhiya", "badiya", "chal", "raha", "rahi", "kar", "kr", "ho",
        "bhai", "yaar", "bol", "bata", "kar", "tha", "thi",
    }
    tokens = re.findall(r"[a-zA-Z]+", low)
    hit_count = sum(1 for tok in tokens if tok in markers)
    return hit_count >= 2


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
    """Safety check: detect self-harm or suicide intent."""
    low = (text or "").lower().strip()
    harmful_keywords = [
        "suicide", "kill myself", "kill me", "end my life", "end it",
        "harm myself", "hurt myself", "cut myself", "self harm", "selfharm",
        "marna hai", "maut chahiye", "apne aap ko hurt", "zehreela peena",
    ]
    return any(keyword in low for keyword in harmful_keywords)


def _get_safety_response(persona: dict[str, str]) -> str:
    nick = (persona.get("nickname") or "dost").strip()
    responses = [
        f"{nick}, jo bhi chal raha hai — please kisi se baat kar. "
        "iChance helpline: 9152987821. Tu important hai.",
        f"{nick}, ye sun: tu akela nahi hai. "
        "Please apne kisi karib se baat kar ya iCall helpline pe call kar: 9152987821.",
        f"{nick}, abhi ye sab side me rakh aur ek kaam kar — "
        "kisi ek dost ya family member ko call kar. Bas ek. Tu zaruri hai.",
    ]
    return random.choice(responses)


# ── Brain Agent ────────────────────────────────────────────────────────────────

class BrainAgent:
    """
    LLM-first brain: every message goes to Groq, response comes back as-is.
    No guard overrides. No canned replies. Just the real LLM.

    Args:
        model:         Groq model id, e.g. ``"llama-3.1-8b-instant"``
        groq_api_key:  Groq API key (or reads from GROQ_API_KEY env var).
        groq_url:      Groq OpenAI-compatible endpoint.
    """

    def __init__(
        self,
        model: str = "llama-3.1-8b-instant",
        groq_api_key: str | None = None,
        groq_url: str = "https://api.groq.com/openai/v1/chat/completions",
    ) -> None:
        self.model = model
        self.groq_api_key = (groq_api_key or os.getenv("GROQ_API_KEY") or "").strip()
        self.groq_url = groq_url
        self.conversation_history: list[dict[str, str]] = []

    def _has_groq_key(self) -> bool:
        return bool(self.groq_api_key)

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
        Process user input and return the LLM's response directly.

        Returns::

            {
                "intent":   "conversation",
                "action":   None,
                "response": "<reply text>",
                "emotion":  "<emotion>",
                "tts_text": "<reply text>"
            }
        """
        history = history or []
        sys_prompt = system_prompt or JARVIS_SYSTEM
        persona = self._extract_persona(sys_prompt)

        original_text = user_text.strip()
        if not original_text:
            return {
                "intent": "conversation",
                "action": None,
                "response": "Haan, bol na.",
                "emotion": "neutral",
                "tts_text": "Haan, bol na.",
            }

        self._append_conversation("user", original_text)

        # Detect language + emotion (for TTS + context hints)
        is_hindi_or_hinglish_input = _is_hindi_or_hinglish(original_text)
        emotion = _detect_emotion(original_text)
        print(f"[Brain] Hinglish={is_hindi_or_hinglish_input}, Emotion={emotion}")

        # ── ONLY deterministic override: safety check ──────────────────────
        if _contains_harmful_keywords(original_text):
            print("[Safety] Harmful intent detected — overriding with safety response.")
            safety_response = _get_safety_response(persona)
            self._append_conversation("assistant", safety_response)
            return {
                "intent": "conversation",
                "action": None,
                "response": safety_response,
                "emotion": "sadness",
                "tts_text": safety_response,
            }

        # ── Build message list for LLM ─────────────────────────────────────
        messages: list[dict] = [{"role": "system", "content": sys_prompt}]

        # Add emotion context hint if user has been consistently low/happy
        if user_id:
            try:
                if conversation_id:
                    db_history = get_messages(user_id, conversation_id)
                else:
                    db_history = get_chat_history(user_id, companion_id)

                recent_emotions = [
                    (msg.get("emotion") or "").lower()
                    for msg in db_history
                    if msg.get("emotion")
                ][-4:]
                if recent_emotions.count("sadness") >= 3:
                    messages.append({
                        "role": "system",
                        "content": "Note: User has been feeling low for a while. Be extra warm and present.",
                    })
                elif recent_emotions.count("joy") >= 3:
                    messages.append({
                        "role": "system",
                        "content": "Note: User has been in a good mood. Match their positive energy.",
                    })

                # Last 10 turns of history for good context
                for msg in db_history[-10:]:
                    role = msg.get("role")
                    content = (msg.get("message") or "").strip()
                    if role in {"user", "assistant"} and content:
                        messages.append({"role": role, "content": content})

            except Exception as e:
                print(f"[History Load Error] {e}")
        else:
            # Unauthenticated: use in-process conversation memory
            memory_slice = self.conversation_history[-10:]
            if memory_slice and memory_slice[-1].get("role") == "user":
                memory_slice = memory_slice[:-1]
            messages.extend(memory_slice)

        messages.append({"role": "user", "content": original_text})

        # ── Call LLM and return its response directly ──────────────────────
        response_text = self._call_groq(messages)

        if not response_text:
            # LLM failed — minimal honest fallback (not canned)
            response_text = (
                "Groq se response nahi aaya abhi. "
                "Thoda ruk ke dobara try kar."
            )

        # Strip only hard AI meta-preambles (e.g. "As an AI language model...")
        response_text = self._strip_ai_preamble(response_text)

        self._append_conversation("assistant", response_text)
        return {
            "intent": "conversation",
            "action": None,
            "response": response_text,
            "emotion": emotion,
            "tts_text": response_text,
        }

    def _append_conversation(self, role: str, content: str) -> None:
        if role not in {"user", "assistant"}:
            return
        text = (content or "").strip()
        if not text:
            return
        self.conversation_history.append({"role": role, "content": text})
        if len(self.conversation_history) > 20:
            self.conversation_history = self.conversation_history[-20:]

    @staticmethod
    def _strip_ai_preamble(text: str) -> str:
        """Strip 'As an AI...' type openers. Do NOT modify actual content."""
        cleaned = (text or "").strip()
        cleaned = re.sub(
            r"^(As an AI(?: language model)?[,.]?\s*)",
            "", cleaned, flags=re.IGNORECASE
        )
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    @staticmethod
    def _extract_persona(system_prompt: str | None) -> dict[str, str]:
        text = system_prompt or ""
        out = {
            "name": "Aira",
            "relationship": "companion",
            "nickname": "dost",
            "style": "casual",
            "language": "hinglish",
        }
        for key, pattern in [
            ("name", r"-\s*Name:\s*(.+)"),
            ("relationship", r"-\s*Relationship to user:\s*(.+)"),
            ("nickname", r'always call them:\s*"([^"]+)"'),
            ("style", r"-\s*Personality style:\s*(.+)"),
            ("language", r"-\s*Preferred neutral language:\s*(.+)"),
        ]:
            m = re.search(pattern, text, flags=re.IGNORECASE)
            if m:
                out[key] = m.group(1).strip()
        return out

    # ── Groq HTTP call ──────────────────────────────────────────────────────

    def _call_groq(self, messages: list) -> str:
        if not self._has_groq_key():
            print("[BrainAgent] No Groq API key configured.")
            return ""

        start_time = time.time()
        candidates = [
            self.model,
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
        ]
        seen: set[str] = set()

        for model_name in candidates:
            if not model_name or model_name in seen:
                continue
            seen.add(model_name)
            try:
                payload = {
                    "model": model_name,
                    "messages": messages,
                    "temperature": 0.80,   # slightly higher = more natural/varied
                    "top_p": 0.92,
                    "max_tokens": 400,
                }
                resp = requests.post(
                    self.groq_url,
                    headers={
                        "Authorization": f"Bearer {self.groq_api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=(10, 60),
                )
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices") or []
                text = ""
                if choices:
                    msg = (choices[0] or {}).get("message") or {}
                    content = msg.get("content")
                    if isinstance(content, str):
                        text = content.strip()
                if text:
                    if model_name != self.model:
                        print(f"[BrainAgent] Fallback model used: {model_name}")
                    print(f"[LLM Time]: {time.time() - start_time:.2f}s")
                    return text
            except requests.exceptions.HTTPError as exc:
                print(f"[BrainAgent] Model {model_name} HTTP error: {exc}")
                continue
            except Exception as exc:
                print(f"[BrainAgent] Model {model_name} failed: {exc}")
                continue

        print(f"[LLM Time]: {time.time() - start_time:.2f}s — all models failed")
        return ""
