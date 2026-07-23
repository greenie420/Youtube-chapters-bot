"""Rejects AI output that wouldn't make a good chapter list."""


def validate_chapters(chapters, duration_seconds):
    if not chapters:
        return False, "no chapters returned"
    if len(chapters) < 3:
        return False, "fewer than 3 chapters (YouTube requires at least 3 to render them)"
    if chapters[0]["seconds"] != 0:
        return False, "first chapter does not start at 00:00"

    seen_titles = set()
    for i, c in enumerate(chapters):
        title = c["title"].strip()

        if not (2 <= len(title) <= 100):
            return False, f"chapter title has an invalid length: '{title}'"

        if title.lower() in seen_titles:
            return False, f"duplicate chapter title: '{title}'"
        seen_titles.add(title.lower())

        if i > 0 and c["seconds"] <= chapters[i - 1]["seconds"]:
            return False, "timestamps are not in ascending order"

        next_boundary = (
            chapters[i + 1]["seconds"] if i + 1 < len(chapters) else duration_seconds
        )
        if next_boundary - c["seconds"] < 10:
            return False, f"chapter '{title}' is shorter than 10 seconds"

    return True, "ok"
