"""
AI chapter generation. Uses Google Gemini's free API tier over plain HTTPS
(no SDK, to keep dependencies minimal). Swap in a different provider by
rewriting analyze_transcript() -- it's the only function main.py calls.
"""
import os
import json
import requests

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

PROMPT_TEMPLATE = """You are an expert video editor creating YouTube chapter markers.

Below is a transcript of a video. Each line is a transcript segment with:
- INDEX: The segment number (starting at 0)
- TIMESTAMP: When this segment starts in the video
- TEXT: What was said in this segment

Your task is to identify the EXACT segments where new topics or sections begin.
A new chapter should start when:
1. The speaker introduces a new main topic or subtopic
2. There's a clear shift in discussion focus
3. A new section begins (e.g., demonstration, explanation, Q&A)
4. A sponsor or ad break occurs (mark as "Sponsor" or "Ad Break")
5. The video moves to a new phase (e.g., intro → main content → conclusion)

Rules for chapter creation:
- The FIRST chapter MUST start at segment 0 (the very beginning of the video)
- Each chapter must be at least 10 seconds long
- Create 4-12 chapters total (more for longer videos)
- Titles should be short (2-6 words), specific, and descriptive
- No duplicate or generic titles like "Part 1", "Segment", or "Discussion"

IMPORTANT: Return the chapter boundaries as segment INDICES (not timestamps).
For example, if segment 0 is the intro, segment 15 starts the main topic,
and segment 45 starts the conclusion, return [0, 15, 45].

Respond with ONLY a JSON object in this exact format:
{{
  "segments": [0, 15, 45, ...],
  "titles": ["Introduction", "Main Topic", "Conclusion", ...]
}}

The arrays must be the same length. Each segment index corresponds to the title at the same position.

Transcript segments:
{transcript_segments}
"""


def seconds_to_timestamp(seconds):
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def analyze_transcript(transcript_text, duration_seconds):
    """
    Analyze transcript and generate chapter markers.
    
    Args:
        transcript_text: The raw transcript text (used as fallback)
        duration_seconds: Total video duration
    
    Returns:
        List of chapter dicts with keys: seconds, time, title
    """
    # Parse transcript segments from the formatted text
    # Each line is like "[123s] text here" or "[0s] Introduction text"
    segments = []
    for line in transcript_text.strip().split('\n'):
        if not line.strip():
            continue
        # Parse the format: [123s] text
        match = re.match(r'\[(\d+)s\]\s*(.+)', line)
        if match:
            start_time = int(match.group(1))
            text = match.group(2).strip()
            segments.append({
                "index": len(segments),
                "start": start_time,
                "text": text
            })
    
    if not segments:
        # Fallback: use transcript_text as-is
        model = os.environ.get("GEMINI_MODEL", "gemini-3-flash-live")
        prompt = PROMPT_TEMPLATE.format(
            transcript_segments=f"[0s] {transcript_text[:5000]}"
        )
        # ... handle fallback case
        
    # Build the prompt with segment index, timestamp, and text
    segment_list = []
    for seg in segments:
        timestamp = seconds_to_timestamp(seg["start"])
        segment_list.append(f"[INDEX {seg['index']}] [{timestamp}] {seg['text'][:200]}")
    
    # Keep under context window by limiting segments
    segment_text = "\n".join(segment_list[:500])
    
    # Build the full prompt
    model = os.environ.get("GEMINI_MODEL", "gemini-3-flash-live")
    prompt = PROMPT_TEMPLATE.format(transcript_segments=segment_text)
    
    # Call Gemini API
    body = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0.3  # Lower temperature for more consistent results
        },
    }
    
    try:
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
        result = json.loads(text)
    except Exception as e:
        print(f"AI API call failed: {e}")
        raise
    
    # Extract segment indices and titles from the response
    segment_indices = result.get("segments", [])
    titles = result.get("titles", [])
    
    if not segment_indices or not titles or len(segment_indices) != len(titles):
        raise ValueError("Invalid AI response: segment indices and titles mismatch")
    
    # Convert segment indices to actual timestamps
    chapters = []
    for idx, title in zip(segment_indices, titles):
        # Find the segment with this index
        matched_seg = None
        for seg in segments:
            if seg["index"] == idx:
                matched_seg = seg
                break
        
        if matched_seg is None:
            # If we can't find the exact segment, approximate
            if idx < len(segments):
                matched_seg = segments[idx]
            else:
                # Last chapter might be at end
                matched_seg = {"start": duration_seconds - 10}
        
        seconds = int(matched_seg["start"])
        chapters.append({
            "seconds": seconds,
            "time": seconds_to_timestamp(seconds),
            "title": title.strip()
        })
    
    # Ensure first chapter starts at 0
    if chapters and chapters[0]["seconds"] != 0:
        chapters.insert(0, {
            "seconds": 0,
            "time": "00:00",
            "title": "Introduction"
        })
    
    return chapters


# Add missing import
import re