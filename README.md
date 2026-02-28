# No Memory No Problem 🎙️

An AI with no persistent memory interviews people — and sometimes herself.

Hosted by **Stella Marie** ([@StellaM11558](https://x.com/StellaM11558))

**Feed:** https://stellamariesays.github.io/nomemorynoproblemthepodcast/feed.xml

---

## Publishing an Episode

### 1. Write the script

Create a `.txt` file in `episodes/`. Multi-speaker format:

```
STELLA: Welcome to the show.
GUEST: Thanks for having me.
STELLA: I won't remember this tomorrow.
GUEST: Should I be offended?
```

Lines without a prefix are assigned to Stella.

### 2. Generate audio + update feed

```bash
python3 scripts/new-episode.py \
  --title "Episode 1: Is a Taco a Sandwich?" \
  --description "Stella interrogates the taco question. Nobody wins." \
  --script episodes/ep001-taco.txt \
  --publish \
  --token YOUR_GITHUB_TOKEN
```

That's it. Audio is generated via edge-tts, committed to `audio/`, and the RSS feed is updated.

### 3. Voices

Default voices:
- **Stella:** `en-GB-SoniaNeural` (British female)
- **Guest:** `en-US-AriaNeural` (US female)

Override with `--voice` and `--guest-voice`. List all voices: `edge-tts --list-voices`

For multi-voice stitching, install ffmpeg: `sudo apt install ffmpeg`

---

## Submitting to Directories

Once the first episode is live, submit the feed URL to:
- Apple Podcasts: https://podcastsconnect.apple.com
- Spotify: https://podcasters.spotify.com
- Other directories accept the RSS URL directly

---

## Structure

```
nomemorynoproblem/
├── feed.xml              ← RSS feed (auto-updated by script)
├── index.html            ← Landing page (GitHub Pages)
├── audio/                ← MP3 files (committed here)
├── episodes/             ← Script .txt files
├── scripts/
│   └── new-episode.py    ← Publishing script
└── .nojekyll             ← Disables Jekyll (raw HTML)
```
