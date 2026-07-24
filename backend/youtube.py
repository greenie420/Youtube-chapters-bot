"""
All interaction with YouTube: reading channel/video metadata through the
official Data API, pulling transcripts (unofficial, no key required), and
posting a chapters comment through OAuth.
"""
import os
import re
import requests
from supadata import Supadata

API_BASE = "https://www.googleapis.com/youtube/v3"


def api_get(endpoint, params):
    params = dict(params)
    params["key"] = os.environ["YOUTUBE_API_KEY"]
    r = requests.get(f"{API_BASE}/{endpoint}", params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def get_uploads_playlist_id(channel_id):
    """Every channel has a hidden 'uploads' playlist -- listing it is the
    cheapest way (1 quota unit) to see a channel's videos, newest first."""
    data = api_get("channels", {"part": "contentDetails", "id": channel_id})
    items = data.get("items", [])
    if not items:
        raise ValueError(f"channel not found: {channel_id}")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def list_recent_videos(uploads_playlist_id, max_results=5):
    data = api_get(
        "playlistItems",
        {
            "part": "snippet",
            "playlistId": uploads_playlist_id,
            "maxResults": max_results,
        },
    )
    videos = []
    for item in data.get("items", []):
        sn = item["snippet"]
        if sn.get("title") in ("Private video", "Deleted video"):
            continue
        thumbs = sn["thumbnails"]
        thumb = thumbs.get("high") or thumbs.get("medium") or thumbs["default"]
        videos.append(
            {
                "videoId": sn["resourceId"]["videoId"],
                "title": sn["title"],
                "published": sn["publishedAt"],
                "thumbnail": thumb["url"],
            }
        )
    return videos


def parse_iso8601_duration(iso):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    h, mnt, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mnt * 60 + s


def get_video_duration(video_id):
    data = api_get("videos", {"part": "contentDetails", "id": video_id})
    items = data.get("items", [])
    if not items:
        return None
    iso = items[0]["contentDetails"]["duration"]
    return {"iso": iso, "seconds": parse_iso8601_duration(iso)}


def get_transcript(video_id, languages=("en",)):
    """Fetch transcript using Supadata API."""
    client = Supadata(api_key=os.environ["SUPADATA_API_KEY"])
    try:
        # Supadata returns a dict, not an object with attributes
        resp = client.transcript(url=f"https://www.youtube.com/watch?v={video_id}")
    except Exception as e:
        print(f"  transcript fetch failed: {e}")
        return None
    
    # Handle both dict response and potential attribute-style access
    if isinstance(resp, dict):
        content = resp.get("content", [])
        lang = resp.get("lang")
    else:
        # Fallback for if it returns an object (unlikely but defensive)
        content = getattr(resp, "content", [])
        lang = getattr(resp, "lang", None)
    
    # Parse segments from content
    segments = []
    for item in content:
        if isinstance(item, dict):
            segments.append({
                "text": item.get("text", ""),
                "start": item.get("offset", 0.0),
                "duration": item.get("duration", 0)
            })
        else:
            # If it's an object with attributes
            segments.append({
                "text": getattr(item, "text", ""),
                "start": getattr(item, "offset", 0.0),
                "duration": getattr(item, "duration", 0)
            })
    
    return {
        "language_code": lang or "en",
        "source": "supadata",
        "segments": segments
    }


def get_access_token(client_id, client_secret, refresh_token):
    r = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def post_comment(video_id, text, access_token):
    r = requests.post(
        f"{API_BASE}/commentThreads",
        params={"part": "snippet"},
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "snippet": {
                "videoId": video_id,
                "topLevelComment": {"snippet": {"textOriginal": text}},
            }
        },
        timeout=30,
    )
    r.raise_for_status()
    return r.json()