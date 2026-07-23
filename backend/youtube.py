"""
All interaction with YouTube: reading channel/video metadata through the
official Data API, pulling transcripts (unofficial, no key required), and
posting a chapters comment through OAuth.
"""
import os
import re
import requests
from youtube_transcript_api import YouTubeTranscriptApi

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
    """Prefer a human-written transcript; fall back to auto-captions.
    Returns None (and logs why) if no transcript could be retrieved --
    e.g. captions are disabled, or YouTube is rate-limiting this IP
    (common on cloud hosts like GitHub Actions runners)."""
    ytt_api = YouTubeTranscriptApi()
    try:
        transcript_list = ytt_api.list(video_id)
    except Exception as e:
        print(f"  transcript list failed: {e}")
        return None

    transcript = None
    try:
        transcript = transcript_list.find_manually_created_transcript(list(languages))
    except Exception:
        try:
            transcript = transcript_list.find_transcript(list(languages))
        except Exception as e:
            print(f"  no transcript in {languages}: {e}")
            return None

    try:
        fetched = transcript.fetch()
    except Exception as e:
        print(f"  transcript fetch failed: {e}")
        return None

    return {
        "language_code": transcript.language_code,
        "source": "youtube_auto" if transcript.is_generated else "youtube_manual",
        "segments": [{"text": s.text, "start": s.start} for s in fetched],
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
