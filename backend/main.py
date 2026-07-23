"""
Entry point. Run as `python backend/main.py` from the repo root (the GitHub
Actions workflow does exactly this on a schedule).

For each enabled channel in config/channels.json:
  1. list its most recent uploads
  2. skip any video that already has a JSON file (idempotent)
  3. fetch a transcript
  4. ask the AI module for chapters
  5. validate them
  6. write channels/<channelId>/<videoId>.json
  7. optionally post a YouTube comment
  8. update channels/index.json (the file the frontend reads)

The workflow commits and pushes whatever ends up in channels/ afterwards.
"""
import os
import json
import datetime
import pathlib

import ai
import validate
import youtube

ROOT = pathlib.Path(__file__).resolve().parent.parent
CHANNELS_DIR = ROOT / "channels"
CONFIG_PATH = ROOT / "config" / "channels.json"
INDEX_PATH = CHANNELS_DIR / "index.json"


def load_config():
    with open(CONFIG_PATH) as f:
        return json.load(f)


def load_index():
    if INDEX_PATH.exists():
        return json.loads(INDEX_PATH.read_text())
    return {"updated": None, "stats": {}, "channels": [], "videos": []}


def save_index(index):
    INDEX_PATH.write_text(json.dumps(index, indent=2, ensure_ascii=False))


def build_comment_text(chapters):
    lines = ["Chapters", ""]
    lines += [f"{c['time']} {c['title']}" for c in chapters]
    lines += ["", "Generated automatically."]
    return "\n".join(lines)


def update_index(index, record):
    videos = [v for v in index["videos"] if v["videoId"] != record["videoId"]]
    videos.append(
        {
            "videoId": record["videoId"],
            "title": record["title"],
            "channelId": record["channelId"],
            "channelName": record["channelName"],
            "published": record["published"],
            "duration": record["duration"],
            "thumbnail": record["thumbnail"],
            "chapterTitles": [c["title"] for c in record["chapters"]],
            "commentPosted": record["comment"]["posted"],
        }
    )
    videos.sort(key=lambda v: v["published"], reverse=True)
    index["videos"] = videos

    channels = {c["id"]: c for c in index["channels"]}
    ch = channels.get(record["channelId"], {"id": record["channelId"]})
    ch["name"] = record["channelName"]
    ch["videoCount"] = sum(1 for v in videos if v["channelId"] == record["channelId"])
    ch["lastUpdate"] = record["generated"]
    channels[record["channelId"]] = ch
    index["channels"] = sorted(channels.values(), key=lambda c: c["name"].lower())

    index["stats"] = {
        "videos": len(videos),
        "channels": len(index["channels"]),
        "comments": sum(1 for v in videos if v["commentPosted"]),
        "avgChapters": (
            round(sum(len(v["chapterTitles"]) for v in videos) / len(videos), 1)
            if videos
            else 0
        ),
    }
    index["updated"] = datetime.datetime.utcnow().isoformat() + "Z"


def process_video(channel_cfg, video_meta, index):
    video_id = video_meta["videoId"]
    channel_id = channel_cfg["id"]
    out_path = CHANNELS_DIR / channel_id / f"{video_id}.json"

    if out_path.exists():
        return False  # already processed -- this IS the idempotency check

    print(f"  -> {video_meta['title']} ({video_id})")

    duration = youtube.get_video_duration(video_id)
    if not duration:
        print("     could not read video duration, skipping")
        return False

    transcript = youtube.get_transcript(video_id)
    if not transcript:
        print("     no transcript available, skipping")
        return False

    transcript_text = "\n".join(
        f"[{int(s['start'])}s] {s['text']}" for s in transcript["segments"]
    )

    try:
        chapters = ai.analyze_transcript(transcript_text, duration["seconds"])
    except Exception as e:
        print(f"     AI analysis failed: {e}")
        return False

    ok, reason = validate.validate_chapters(chapters, duration["seconds"])
    if not ok:
        print(f"     validation failed: {reason}")
        return False

    comment_info = {"posted": False, "id": None, "url": None}
    if channel_cfg.get("comment") and os.environ.get("YT_REFRESH_TOKEN"):
        try:
            token = youtube.get_access_token(
                os.environ["YT_CLIENT_ID"],
                os.environ["YT_CLIENT_SECRET"],
                os.environ["YT_REFRESH_TOKEN"],
            )
            result = youtube.post_comment(video_id, build_comment_text(chapters), token)
            comment_id = result["id"]
            comment_info = {
                "posted": True,
                "id": comment_id,
                "url": f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}",
            }
            print("     comment posted")
        except Exception as e:
            print(f"     comment posting failed: {e}")

    record = {
        "videoId": video_id,
        "title": video_meta["title"],
        "channelId": channel_id,
        "channelName": channel_cfg["name"],
        "published": video_meta["published"],
        "duration": duration["iso"],
        "durationSeconds": duration["seconds"],
        "thumbnail": video_meta["thumbnail"],
        "transcriptSource": transcript["source"],
        "transcriptLanguage": transcript["language_code"],
        "chapters": chapters,
        "comment": comment_info,
        "generated": datetime.datetime.utcnow().isoformat() + "Z",
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(record, indent=2, ensure_ascii=False))
    update_index(index, record)
    return True


def main():
    config = load_config()
    index = load_index()

    for ch in config["channels"]:
        if not ch.get("enabled", True):
            continue
        print(f"=== {ch['name']} ===")
        try:
            uploads_id = youtube.get_uploads_playlist_id(ch["id"])
            videos = youtube.list_recent_videos(uploads_id, ch.get("max_videos", 5))
        except Exception as e:
            print(f"  failed to list videos: {e}")
            continue

        for v in videos:
            try:
                process_video(ch, v, index)
            except Exception as e:
                print(f"  unexpected error on {v['videoId']}: {e}")

    CHANNELS_DIR.mkdir(parents=True, exist_ok=True)
    save_index(index)
    print("Done.")


if __name__ == "__main__":
    main()
