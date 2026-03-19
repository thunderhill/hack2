"""Audio processing for Travel Itinerary Generator — Whisper transcription + intent extraction."""

import json
import io
from .config import get_llm_client, get_model

WHISPER_MODEL = "azure/genailab-maas-whisper"

# ── Transcription ─────────────────────────────────────────────────────────────

def transcribe_audio(audio_bytes: bytes, filename: str = "audio.wav") -> str:
    """Transcribe audio bytes using Whisper via TCS GenAI proxy."""
    client = get_llm_client()
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename  # OpenAI SDK uses filename for MIME type detection

    transcript = client.audio.transcriptions.create(
        model=WHISPER_MODEL,
        file=audio_file,
        response_format="text",
    )
    return transcript.strip() if isinstance(transcript, str) else transcript.text.strip()


# ── Intent Extraction ─────────────────────────────────────────────────────────

_EXTRACT_SYSTEM_PROMPT = """You are a travel assistant that extracts structured travel request details from spoken or written text.

Extract the following fields from the user's request:
- destination: The travel destination (city, country, or region). Required.
- duration_days: Number of days as an integer (1-30). Default to 5 if not mentioned.
- budget: One of exactly: "budget", "mid-range", or "luxury". Infer from context (e.g. "cheap" → "budget", "5-star" → "luxury"). Default "mid-range".
- interests: Comma-separated list of interests/activities mentioned (e.g. "temples, food, hiking"). Required.
- travel_month: Month of travel if mentioned (e.g. "June", "next December"). Empty string if not mentioned.
- confidence: "high" if destination and interests are clear, "medium" if inferred, "low" if very uncertain.
- notes: Any clarification needed from the user (empty string if all clear).

Respond ONLY with valid JSON. No markdown, no explanation."""

_EXTRACT_USER_TEMPLATE = """Extract travel request details from this text:

"{transcript}"

Return JSON with keys: destination, duration_days, budget, interests, travel_month, confidence, notes."""


def extract_travel_intent(transcript: str, model_key: str = "gpt-4o-mini") -> dict:
    """Use LLM to extract structured travel parameters from a transcript."""
    client = get_llm_client()
    deployment = get_model(model_key)

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": _EXTRACT_SYSTEM_PROMPT},
            {"role": "user", "content": _EXTRACT_USER_TEMPLATE.format(transcript=transcript)},
        ],
        max_tokens=512,
        temperature=0.1,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    if raw.endswith("```"):
        raw = raw[:-3]

    data = json.loads(raw)

    # Ensure required fields with defaults
    return {
        "destination":   data.get("destination", ""),
        "duration_days": int(data.get("duration_days", 5)),
        "budget":        data.get("budget", "mid-range"),
        "interests":     data.get("interests", ""),
        "travel_month":  data.get("travel_month", ""),
        "confidence":    data.get("confidence", "medium"),
        "notes":         data.get("notes", ""),
    }
