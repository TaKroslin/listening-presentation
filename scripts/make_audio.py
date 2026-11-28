#!/usr/bin/env python3
"""
Free male-voice TTS for the listening deck (Microsoft Edge voices via edge-tts).

* no API key, no cost
* per-paragraph synthesis, joined with silence so students get a beat to write
* loudness-normalised to -16 LUFS for classroom playback

Usage:
    python make_audio.py --text article.txt --out listening.mp3
    python make_audio.py --text article.txt --out listening.mp3 --voice en-US-ChristopherNeural

Voices worth trying (all male, all free):
    en-US-AndrewNeural       warm, natural, best all-rounder (default)
    en-US-ChristopherNeural  news-anchor authority
    en-GB-RyanNeural         British, friendly
"""
import argparse
import asyncio
import os
import subprocess
import sys
import tempfile
import time
import wave

import edge_tts



# Curated classroom voices (all free, all edge-tts).
# key, voice id, gender, accent, character
VOICES = [
    ("A", "en-US-AndrewNeural",               "男", "美音", "温暖、自然，最像真人播客（默认）"),
    ("B", "en-US-ChristopherNeural",          "男", "美音", "新闻主播，权威、字正腔圆"),
    ("C", "en-US-GuyNeural",                  "男", "美音", "新闻/小说，情绪饱满"),
    ("D", "en-US-BrianNeural",                "男", "美音", "随和、口语化"),
    ("E", "en-GB-RyanNeural",                 "男", "英音", "友好、清晰"),
    ("F", "en-GB-ThomasNeural",               "男", "英音", "冷静、标准 RP"),
    ("G", "en-AU-WilliamMultilingualNeural",  "男", "澳音", "澳洲口音，轻松"),
    ("H", "en-CA-LiamNeural",                 "男", "加拿大音", "北美口音，平和"),
    ("I", "en-IN-PrabhatNeural",              "男", "印度音", "印度口音，清晰"),
    ("J", "en-US-AriaNeural",                 "女", "美音", "新闻主播，积极自信"),
    ("K", "en-US-JennyNeural",                "女", "美音", "亲切、耐心"),
    ("L", "en-US-AvaNeural",                  "女", "美音", "生动、有表现力"),
    ("M", "en-US-EmmaNeural",                 "女", "美音", "明亮、口语化"),
    ("N", "en-GB-SoniaNeural",                "女", "英音", "英音新闻，端庄"),
    ("O", "en-GB-LibbyNeural",                "女", "英音", "明亮、年轻"),
    ("P", "en-AU-NatashaNeural",              "女", "澳音", "澳洲口音，友善"),
    ("Q", "en-IN-NeerjaNeural",               "女", "印度音", "印度口音，清楚"),
]


def print_voices():
    print("可用配音（edge-tts，免费）：")
    print("key  voice-id                         性别  口音      特点")
    for key, vid, gender, accent, desc in VOICES:
        print("%-4s %-32s %-4s  %-8s  %s" % (key, vid, gender, accent, desc))
    print()
    print("默认：A（en-US-AndrewNeural），语速 +3%。")
    print("也可以直接用 --voice <任意 edge-tts 音色 id>。")


def synth(text, voice, rate, out_path, attempts=4):
    async def _run():
        comm = edge_tts.Communicate(text, voice, rate=rate)
        await comm.save(out_path)

    last = None
    for i in range(attempts):
        try:
            asyncio.run(_run())
            if os.path.getsize(out_path) > 1024:
                return
        except Exception as e:  # transient edge service errors happen
            last = e
        time.sleep(1.5 * (i + 1))
    raise RuntimeError("edge-tts failed after %d attempts: %s" % (attempts, last))


def to_wav(src, dst):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", src, "-ar", "44100", "-ac", "1", dst],
        check=True,
    )


def read_frames(path):
    with wave.open(path, "rb") as w:
        return w.readframes(w.getnframes()), w.getframerate()


def silence_wav(path, seconds, sr=44100):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(b"\x00\x00" * int(sr * seconds))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--text", help="UTF-8 text file, paragraphs separated by blank lines")
    ap.add_argument("--list-voices", action="store_true", help="print the curated voice menu and exit")
    ap.add_argument("--out")
    ap.add_argument("--voice", default="en-US-AndrewNeural")
    ap.add_argument("--rate", default="-5%", help="e.g. -8%% for slower dictation pace")
    ap.add_argument("--note", default="", help="optional spoken lead-in, e.g. 'Listen to the news report.'")
    ap.add_argument("--sentence-gap", type=float, default=0.45)
    ap.add_argument("--paragraph-gap", type=float, default=1.0)
    args = ap.parse_args()

    if args.list_voices:
        print_voices()
        return
    if not args.text or not args.out:
        raise SystemExit("--text and --out are required (or use --list-voices)")

    with open(args.text, encoding="utf-8") as f:
        raw = f.read().strip()
    paragraphs = [p.strip().replace("\n", " ") for p in raw.split("\n\n") if p.strip()]

    tmp = tempfile.mkdtemp(prefix="tts-")
    sr = 44100
    frame_all = []

    sil_short = os.path.join(tmp, "s_short.wav")
    sil_long = os.path.join(tmp, "s_long.wav")
    silence_wav(sil_short, args.sentence_gap, sr)
    silence_wav(sil_long, args.paragraph_gap, sr)
    short_frames, _ = read_frames(sil_short)
    long_frames, _ = read_frames(sil_long)

    if args.note:
        note_mp3 = os.path.join(tmp, "note.mp3")
        synth(args.note, args.voice, args.rate, note_mp3)
        note_wav = os.path.join(tmp, "note.wav")
        to_wav(note_mp3, note_wav)
        f, _ = read_frames(note_wav)
        frame_all.append(f)
        frame_all.append(long_frames)

    for i, para in enumerate(paragraphs):
        mp3 = os.path.join(tmp, "p%02d.mp3" % i)
        wav = os.path.join(tmp, "p%02d.wav" % i)
        print("  synth paragraph %d/%d (%d chars)" % (i + 1, len(paragraphs), len(para)))
        synth(para, args.voice, args.rate, mp3)
        to_wav(mp3, wav)
        frames, _ = read_frames(wav)
        frame_all.append(frames)
        frame_all.append(long_frames if i < len(paragraphs) - 1 else short_frames)

    merged = os.path.join(tmp, "merged.wav")
    with wave.open(merged, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        for chunk in frame_all:
            w.writeframes(chunk)

    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", merged,
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
         "-codec:a", "libmp3lame", "-b:a", "96k", args.out],
        check=True,
    )
    dur = float(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
         "default=nw=1:nk=1", args.out],
        capture_output=True, text=True).stdout.strip())
    print("saved %s  (%.1fs, %d bytes)" % (args.out, dur, os.path.getsize(args.out)))


if __name__ == "__main__":
    main()
