"""
AI chapter generation. Uses Google Gemini's free API tier over plain HTTPS
(no SDK, to keep dependencies minimal). Swap in a different provider by
rewriting analyze_transcript() -- it's the only function main.py calls.
"""
import os
import json
import requests

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

PROMPT_TEMPLATE = """You are an expert video editor writing YouTube chapter markers.

Below is a transcript of a video roughly {duration_min} minutes long. Each line is
prefixed with its start time in seconds, like [123s].

Create between 4 and 12 chapters that describe the video's real structure. Rules:
- The first chapter MUST start at 0 seconds.
- Chapters must be in strictly ascending order.
- Each chapter must last at least 10 seconds.
- Titles are short (2-6 words), specific to what actually happens, and never
  generic filler like "Part 1", "Segment", or "Discussion".
- No duplicate or near-duplicate titles.

Respond with ONLY a JSON array in this exact shape, nothing else:
[{{"seconds": 0, "title": "Introduction"}}, {{"seconds": 125, "title": "Setting Up The Project"}}]

Transcript:
{transcript}
"""


def seconds_to_timestamp(seconds):
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def analyze_transcript(transcript_text, duration_seconds):
    model = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    prompt = PROMPT_TEMPLATE.format(
        duration_min=round(duration_seconds / 60, 1),
        transcript=transcript_text[:120000],  # keep well under the context window
    )
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json"},
    }
    r = requests.post(
        GEMINI_URL.format(model=model),
        headers={
            "x-goog-api-key": os.environ["GEMINI_API_KEY"],
            "Content-Type": "application/json",
        },
        json=body,
        timeout=120,
    )
    r.raise_for_status()
    data = r.json()
    text = data["candidates"][0]["content"]["parts"][0]["text"]
    raw_chapters = json.loads(text)

    chapters = []
    for c in raw_chapters:
        seconds = int(c["seconds"])
        chapters.append(
            {
                "seconds": seconds,
                "time": seconds_to_timestamp(seconds),
                "title": str(c["title"]).strip(),
            }
        )
    return chapters
