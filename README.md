# Chapters — AI YouTube Chapter Bot & Public Archive

A prototype that watches YouTube channels, asks an AI to write chapter
markers from each video's transcript, and publishes the result as a
searchable static website — all on free infrastructure, with no server to
manage.

## How it's actually hosted, for free

- **Backend = GitHub Actions.** A Python script runs on a cron schedule
  inside a GitHub Actions job. There's no server to rent or keep alive —
  GitHub *is* the compute.
- **Frontend = GitHub Pages.** Plain HTML/CSS/JS, reading directly from JSON
  files. No build step, no framework.
- **Database = the JSON files themselves**, committed straight into the
  repo. The crawler writes `channels/<channelId>/<videoId>.json` for each
  video and `git push`es it — GitHub Pages then serves the update
  automatically.

One repo, two GitHub features (Actions + Pages) you flip on in Settings,
zero paid services.

## Where this simplifies the original spec (and why)

The full spec describes two separate repos, a SQLite job/log database, and
GitHub-API-based commits. For a prototype this adds real infrastructure
without changing what the user experiences, so it's been simplified:

| Spec asked for | This prototype does instead | Why it's equivalent |
|---|---|---|
| SQLite `Videos`/`Jobs` tables to avoid reprocessing | Checks whether `channels/<id>/<video>.json` already exists | The file's existence *is* the "already processed" record — one less moving part |
| Separate frontend/backend repos | One repo, both folders | GitHub Pages serves the whole repo for free either way; two repos only adds sync overhead |
| GitHub API commits | Plain `git commit && git push` inside the Actions job, using the token Actions already provides | Same result, no extra library or API calls |
| `Errors`/`Jobs` log tables | GitHub Actions' own run logs (Actions tab → every run's console output, kept automatically) | Free, already there, no schema to design |

If you outgrow this later, each of these is a clean place to add the
original design back in — nothing here paints you into a corner.

## Known limitation: read this before assuming something's broken

`youtube-transcript-api` (the free transcript library) doesn't use an
official API key — it reads the same caption data your browser does. YouTube
pushes back on that from known cloud IP ranges (AWS, Azure, GCP), and GitHub
Actions runners live on Azure. So **some transcript fetches from GitHub
Actions will fail with a blocked-request error** — the crawler logs it,
skips that video, and tries again on the next scheduled run. It isn't a bug
in the code; it's YouTube rate-limiting the runner's IP.

If that happens more than occasionally for your channels:
- **Simplest fix:** run `python backend/main.py` from your own computer on a
  cron job / Task Scheduler entry instead of (or in addition to) GitHub
  Actions. Same repo, same code — just a residential IP. Still 100% free.
- **Or:** the library has built-in support for a paid residential-proxy
  provider (Webshare) if you want it to run unattended from the cloud
  reliably. Not free, and not required to try the prototype.

## What you'll need (all free, no credit card for the AI)

| # | Account / service | What it's for |
|---|---|---|
| 1 | A GitHub account | Hosts the code, runs the backend (Actions), hosts the site (Pages) |
| 2 | A Google Cloud project + YouTube Data API key | Lets the bot list a channel's videos |
| 3 | A Google AI Studio API key (Gemini) | Generates the chapters |
| 4 | *(Optional)* A Google OAuth "Desktop app" client | Only if you want the bot to post chapters as a YouTube comment on a channel **you own** |

Your GitHub repo needs to be **public** — GitHub Pages is free only for
public repos (private Pages needs a paid plan). That's a fine trade here:
the whole point of the archive is that it's public anyway, and your API
keys stay safe as encrypted GitHub secrets even in a public repo.

---

## Setup

### 1. Create the repo
Create a new **public** GitHub repository and push everything in this
folder to it (`git init`, `git add .`, `git commit -m "initial"`,
`git remote add origin <your repo url>`, `git push -u origin main`).

### 2. Get a YouTube Data API key
1. Go to [console.cloud.google.com](https://console.cloud.google.com) and
   create a new project (or reuse one).
2. **APIs & Services → Library** → search "YouTube Data API v3" → **Enable**.
3. **APIs & Services → Credentials → Create Credentials → API key**.
4. Optional but recommended: click the new key → restrict it to "YouTube
   Data API v3" only.

### 3. Get a Gemini API key
1. Go to [aistudio.google.com](https://aistudio.google.com) → **Get API
   key** → create one in a Google Cloud project. No billing required for
   the free tier.

### 4. Add both keys as repo secrets
In your repo: **Settings → Secrets and variables → Actions → New repository
secret**, and add:
- `YOUTUBE_API_KEY`
- `GEMINI_API_KEY`

### 5. Turn on GitHub Pages
**Settings → Pages → Build and deployment → Source: "Deploy from a
branch"** → Branch: `main`, folder: `/ (root)` → **Save**.
Your site will appear at `https://<your-username>.github.io/<repo-name>/`
after the next push (takes a minute or two the first time).

### 6. Point it at real channels
Edit `config/channels.json`. Replace the example entry with the channel(s)
you want tracked:

```json
{
  "channels": [
    { "id": "UCxxxxxxxxxxxxxxxxxxxxxx", "name": "Some Channel", "enabled": true, "comment": false, "max_videos": 5 }
  ]
}
```

To find a channel ID: open the channel on YouTube → **Share → Copy channel
link** — the ID is the part after `/channel/`. (If the channel uses a
`@handle` URL instead, search "[handle] channel ID" or use any free
channel-ID lookup tool to convert it.)

Commit and push the change.

### 7. Run it
**Actions tab → "Crawl YouTube channels" → Run workflow** (or just wait —
it also runs automatically every 6 hours). Open the workflow run to watch
the logs live. Once it finishes, visit your Pages URL from step 5.

### 8. *(Optional)* Let it post YouTube comments
Only useful for channels **you** own or manage — posting requires that
channel owner's explicit OAuth consent, so this can't post to channels you
don't control.

1. **Google Cloud Console → APIs & Services → OAuth consent screen** →
   configure as "External," publishing status "Testing," and add your own
   Google account under "Test users."
2. **Credentials → Create Credentials → OAuth client ID** → Application
   type **Desktop app** → **Create**, then download the JSON, rename it to
   `client_secret.json`, and place it in `backend/`.
3. On your own computer (not GitHub Actions):
   ```
   pip install -r backend/requirements-setup.txt
   python backend/get_refresh_token.py
   ```
   A browser window opens — log in as the channel owner and approve access.
4. Copy the three values it prints (`YT_CLIENT_ID`, `YT_CLIENT_SECRET`,
   `YT_REFRESH_TOKEN`) into your repo's Actions secrets, same as step 4.
5. Set `"comment": true` for that channel in `config/channels.json`.

---

## Customizing

- **Schedule:** edit the cron expression in
  `.github/workflows/crawl.yml` (`0 */6 * * *` = every 6 hours). Use
  [crontab.guru](https://crontab.guru) to build others.
- **How many videos to check per run:** `max_videos` per channel in
  `config/channels.json` — keep it small to conserve API/AI quota.
- **AI model:** set a `GEMINI_MODEL` repo secret (defaults to
  `gemini-2.5-flash`), or rewrite `analyze_transcript()` in `backend/ai.py`
  to call a different provider entirely — it's the only function the rest
  of the code depends on.
- **Look and feel:** every color, font, and spacing value is a CSS variable
  at the top of `style.css`.

## Repository structure

```
index.html, channel.html, video.html   the site (GitHub Pages serves the repo root)
style.css, app.js                      shared styling and rendering logic
config/channels.json                   which channels to track
channels/                              generated JSON archive (written by the crawler)
  index.json                           summary used by the homepage/search
  <channelId>/<videoId>.json           full record per video
backend/
  main.py                              orchestrator — run this
  youtube.py                           YouTube Data API + transcripts + comment posting
  ai.py                                Gemini chapter generation (swap providers here)
  validate.py                          chapter quality checks
  get_refresh_token.py                 one-time local OAuth setup for comment posting
.github/workflows/crawl.yml            the scheduled job (the "backend host")
```

## Quota notes

- **YouTube Data API:** 10,000 free units/day. Listing a channel and its
  recent uploads costs only a few units, so tracking several channels every
  few hours fits comfortably inside the free tier.
- **Gemini free tier:** a generous daily request allowance with no credit
  card required — see [ai.google.dev/pricing](https://ai.google.dev/pricing)
  for current numbers. One request is used per newly analyzed video, so
  this is rarely the bottleneck unless you're tracking very high-upload
  channels; if you do hit the limit, lower `max_videos` or widen the
  schedule.

## Respecting YouTube's terms

Only enable `"comment": true` for channels you own or are explicitly
authorized to post on behalf of. The crawler makes a small, fixed number of
API calls per run by design — it isn't built to scrape aggressively, and
you shouldn't lower `max_videos`/the schedule interval to try to make it do
so.
