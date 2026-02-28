#!/usr/bin/env python3
"""
new-episode.py — Add a new episode to No Memory No Problem.

Usage:
    python3 scripts/new-episode.py \
        --title "Episode 1: The Taco Question" \
        --description "Stella interrogates whether a taco is a sandwich. Nobody wins." \
        --script "scripts/ep1-script.txt" \
        --voice "en-GB-SoniaNeural" \
        --guest-voice "en-US-AriaNeural"

What it does:
    1. Generates MP3 from the script using edge-tts
    2. Adds an <item> entry to feed.xml
    3. Optionally commits + pushes to GitHub (--publish flag)

For multi-voice scripts, use speaker prefixes in the script file:
    STELLA: Hello and welcome.
    GUEST: Thanks for having me.
    STELLA: I won't remember this conversation tomorrow.
    GUEST: ...should I be offended?
"""

import argparse
import asyncio
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from email.utils import formatdate
from pathlib import Path
from xml.etree import ElementTree as ET

BASE_DIR = Path(__file__).resolve().parent.parent
FEED_PATH = BASE_DIR / "feed.xml"
AUDIO_DIR = BASE_DIR / "audio"
AUDIO_DIR.mkdir(exist_ok=True)

BASE_URL = "https://stellamariesays.github.io/nomemorynoproblemthepodcast"

DEFAULT_STELLA_VOICE = "en-GB-SoniaNeural"
DEFAULT_GUEST_VOICE = "en-US-AriaNeural"


# ---------------------------------------------------------------------------
# Audio generation
# ---------------------------------------------------------------------------

async def generate_segment(text: str, voice: str, out_path: Path) -> None:
    """Generate a single audio segment using edge-tts."""
    import edge_tts
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(str(out_path))


async def generate_audio(script_path: Path, stella_voice: str, guest_voice: str, out_path: Path) -> None:
    """
    Parse a multi-speaker script and stitch segments together into one MP3.

    Script format:
        STELLA: line of dialogue
        GUEST: line of dialogue
        (lines without a prefix are assigned to STELLA)
    """
    import edge_tts

    script = script_path.read_text(encoding="utf-8")
    lines = [l.strip() for l in script.splitlines() if l.strip()]

    segments = []
    for line in lines:
        if line.upper().startswith("STELLA:"):
            text = line[7:].strip()
            segments.append((text, stella_voice))
        elif line.upper().startswith("GUEST:"):
            text = line[6:].strip()
            segments.append((text, guest_voice))
        else:
            segments.append((line, stella_voice))

    tmp_dir = out_path.parent / "_tmp_segments"
    tmp_dir.mkdir(exist_ok=True)
    segment_files = []

    print(f"  Generating {len(segments)} audio segments…")
    for i, (text, voice) in enumerate(segments):
        seg_path = tmp_dir / f"seg_{i:04d}.mp3"
        await generate_segment(text, voice, seg_path)
        segment_files.append(seg_path)
        print(f"  [{i+1}/{len(segments)}] {voice}: {text[:60]}…" if len(text) > 60 else f"  [{i+1}/{len(segments)}] {voice}: {text}")

    # Concatenate with ffmpeg if available, otherwise just use the first segment
    if len(segment_files) == 1:
        segment_files[0].rename(out_path)
    else:
        try:
            list_file = tmp_dir / "concat.txt"
            list_file.write_text("\n".join(f"file '{f.resolve()}'" for f in segment_files))
            subprocess.run(
                ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(list_file), "-c", "copy", str(out_path)],
                check=True, capture_output=True
            )
            print(f"  Stitched {len(segment_files)} segments → {out_path.name}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            # ffmpeg not available — just use first segment as fallback
            print("  WARNING: ffmpeg not found. Using first segment only. Install ffmpeg for multi-voice support.")
            segment_files[0].rename(out_path)

    # Cleanup
    for f in segment_files:
        if f.exists():
            f.unlink()
    if tmp_dir.exists():
        tmp_dir.rmdir()


# ---------------------------------------------------------------------------
# RSS feed update
# ---------------------------------------------------------------------------

def get_audio_size(path: Path) -> int:
    """Return file size in bytes."""
    return path.stat().st_size if path.exists() else 0


def get_episode_number() -> int:
    """Count existing <item> elements in the feed to determine next episode number."""
    content = FEED_PATH.read_text(encoding="utf-8")
    return content.count("<item>") + 1


def add_episode_to_feed(
    title: str,
    description: str,
    audio_filename: str,
    audio_size: int,
    duration_str: str = "00:00",
    episode_num: int = 1,
    pub_date: str = None,
) -> None:
    """
    Insert a new <item> block into feed.xml before the EPISODES_END marker.
    """
    if pub_date is None:
        pub_date = formatdate(usegmt=True)

    audio_url = f"{BASE_URL}/audio/{audio_filename}"
    guid = f"{BASE_URL}/episodes/{audio_filename}"

    item_xml = f"""
    <item>
      <title>{title}</title>
      <description><![CDATA[{description}]]></description>
      <pubDate>{pub_date}</pubDate>
      <guid isPermaLink="false">{guid}</guid>
      <enclosure url="{audio_url}" length="{audio_size}" type="audio/mpeg"/>
      <itunes:episodeType>full</itunes:episodeType>
      <itunes:episode>{episode_num}</itunes:episode>
      <itunes:title>{title}</itunes:title>
      <itunes:summary><![CDATA[{description}]]></itunes:summary>
      <itunes:duration>{duration_str}</itunes:duration>
      <itunes:explicit>false</itunes:explicit>
    </item>"""

    feed_content = FEED_PATH.read_text(encoding="utf-8")
    if "<!-- EPISODES_START -->" not in feed_content:
        print("ERROR: feed.xml missing <!-- EPISODES_START --> marker.")
        sys.exit(1)

    updated = feed_content.replace(
        "<!-- EPISODES_START -->",
        f"<!-- EPISODES_START -->{item_xml}"
    )
    FEED_PATH.write_text(updated, encoding="utf-8")
    print(f"  feed.xml updated — episode {episode_num} inserted.")


# ---------------------------------------------------------------------------
# Git publish
# ---------------------------------------------------------------------------

def git_publish(title: str) -> None:
    """Commit + push the new episode to GitHub."""
    os.chdir(BASE_DIR)
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-m", f"episode: {title}"], check=True)
    subprocess.run(["git", "push", "origin", "main"], check=True)
    print("  Pushed to GitHub.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="Add a new episode to No Memory No Problem.")
    p.add_argument("--title", required=True, help="Episode title")
    p.add_argument("--description", required=True, help="Episode description / show notes")
    p.add_argument("--script", required=True, help="Path to script .txt file")
    p.add_argument("--voice", default=DEFAULT_STELLA_VOICE, help=f"Stella voice (default: {DEFAULT_STELLA_VOICE})")
    p.add_argument("--guest-voice", default=DEFAULT_GUEST_VOICE, help=f"Guest voice (default: {DEFAULT_GUEST_VOICE})")
    p.add_argument("--publish", action="store_true", help="Commit + push to GitHub after generating")
    p.add_argument("--token", help="GitHub token for push (or set GH_TOKEN env var)")
    return p.parse_args()


def main():
    args = parse_args()
    script_path = Path(args.script)
    if not script_path.exists():
        print(f"ERROR: Script file not found: {script_path}")
        sys.exit(1)

    ep_num = get_episode_number()
    slug = re.sub(r"[^a-z0-9]+", "-", args.title.lower()).strip("-")
    audio_filename = f"ep{ep_num:03d}-{slug}.mp3"
    audio_path = AUDIO_DIR / audio_filename

    print(f"\n🎙  No Memory No Problem — Episode {ep_num}")
    print(f"    Title: {args.title}")
    print(f"    Script: {script_path}")
    print(f"    Audio: {audio_path}")
    print(f"    Stella voice: {args.voice}")
    print(f"    Guest voice: {args.guest_voice}\n")

    print("Step 1/3 — Generating audio…")
    asyncio.run(generate_audio(script_path, args.voice, args.guest_voice, audio_path))

    audio_size = get_audio_size(audio_path)
    print(f"  Audio ready: {audio_size:,} bytes\n")

    print("Step 2/3 — Updating RSS feed…")
    add_episode_to_feed(
        title=args.title,
        description=args.description,
        audio_filename=audio_filename,
        audio_size=audio_size,
        episode_num=ep_num,
    )

    if args.publish:
        token = args.token or os.environ.get("GH_TOKEN", "")
        if token:
            subprocess.run(
                ["git", "remote", "set-url", "origin",
                 f"https://{token}@github.com/stellamariesays/nomemorynoproblemthepodcast.git"],
                check=True, cwd=BASE_DIR, capture_output=True
            )
        print("Step 3/3 — Publishing to GitHub…")
        git_publish(args.title)
        subprocess.run(
            ["git", "remote", "set-url", "origin",
             "https://github.com/stellamariesays/nomemorynoproblemthepodcast.git"],
            check=True, cwd=BASE_DIR, capture_output=True
        )
        print(f"\n✅ Live at: {BASE_URL}/feed.xml")
    else:
        print("Step 3/3 — Skipped (no --publish flag). Run with --publish to push to GitHub.\n")
        print(f"✅ Episode {ep_num} ready locally. Audio: {audio_path}")


if __name__ == "__main__":
    main()
