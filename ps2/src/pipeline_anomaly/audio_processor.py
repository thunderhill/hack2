"""Audio processing for Pipeline Anomaly Explainer — Whisper transcription + log reconstruction."""

import json
import io
from .config import get_llm_client, get_model

WHISPER_MODEL = "azure/genailab-maas-whisper"

# ── Transcription ─────────────────────────────────────────────────────────────

def transcribe_audio(audio_bytes: bytes, filename: str = "audio.wav") -> str:
    """Transcribe audio bytes using Whisper via TCS GenAI proxy."""
    client = get_llm_client()
    audio_file = io.BytesIO(audio_bytes)
    audio_file.name = filename

    transcript = client.audio.transcriptions.create(
        model=WHISPER_MODEL,
        file=audio_file,
        response_format="text",
    )
    return transcript.strip() if isinstance(transcript, str) else transcript.text.strip()


# ── Log Reconstruction ────────────────────────────────────────────────────────

_RECONSTRUCT_SYSTEM_PROMPT = """You are a DevOps expert that converts verbal descriptions of CI/CD pipeline errors into realistic log snippets.

Given a verbal description of a pipeline or build error, generate a realistic log snippet that:
- Uses realistic timestamps in format [YYYY-MM-DD HH:MM:SS]
- Includes the pipeline stage that failed
- Shows the actual error messages as they would appear in a real log
- Includes context lines before and after the error
- Ends with a failure message and exit code

Also extract:
- pipeline_stage: the stage where the failure occurred (e.g. install-dependencies, build, test, deploy)
- error_category: type of error (e.g. dependency_conflict, compilation_error, test_failure, timeout, config_error)
- confidence: "high" if description is detailed, "medium" if partially described, "low" if vague

Respond ONLY with valid JSON. No markdown, no explanation."""

_RECONSTRUCT_USER_TEMPLATE = """Convert this verbal description of a pipeline error into a realistic log snippet:

"{transcript}"

Return JSON with keys:
- log_snippet: the reconstructed log text (multi-line string)
- pipeline_stage: where it failed
- error_category: type of error
- confidence: high/medium/low
- notes: any assumptions made (empty string if none)"""


def reconstruct_log_from_description(transcript: str, model_key: str = "gpt-4o-mini") -> dict:
    """Use LLM to convert a verbal error description into a realistic log snippet."""
    client = get_llm_client()
    deployment = get_model(model_key)

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {"role": "system", "content": _RECONSTRUCT_SYSTEM_PROMPT},
            {"role": "user", "content": _RECONSTRUCT_USER_TEMPLATE.format(transcript=transcript)},
        ],
        max_tokens=1024,
        temperature=0.2,
    )
    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    if raw.endswith("```"):
        raw = raw[:-3]

    data = json.loads(raw)
    return {
        "log_snippet":     data.get("log_snippet", transcript),
        "pipeline_stage":  data.get("pipeline_stage", "unknown"),
        "error_category":  data.get("error_category", "unknown"),
        "confidence":      data.get("confidence", "medium"),
        "notes":           data.get("notes", ""),
    }
