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
    client=Supadata(api_key=os.environ["SUPADATA_API_KEY"])
    try:
        resp=client.youtube.transcript(video_id=video_id, mode="native")
    except Exception as e:
        print(f"  transcript fetch failed: {e}")
        return None
    chunks=getattr(resp,"content",None) or resp.get("content",[]) if isinstance(resp,dict) else []
    lang=getattr(resp,"lang",None) or (resp.get("lang") if isinstance(resp,dict) else None)
    segs=[]
    for c in chunks:
        if hasattr(c,"text"):
            segs.append({"text":c.text,"start":getattr(c,"offset",0.0)})
        else:
            segs.append({"text":c.get("text",""),"start":c.get("offset",0.0)})
    return {"language_code":lang,"source":"supadata","segments":segs}

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
