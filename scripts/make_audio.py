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
    ap.add_argument("--text", required=True, help="UTF-8 text file, paragraphs separated by blank lines")
    ap.add_argument("--out", required=True)
    ap.add_argument("--voice", default="en-US-AndrewNeural")
    ap.add_argument("--rate", default="-5%", help="e.g. -8%% for slower dictation pace")
    ap.add_argument("--note", default="", help="optional spoken lead-in, e.g. 'Listen to the news report.'")
    ap.add_argument("--sentence-gap", type=float, default=0.45)
    ap.add_argument("--paragraph-gap", type=float, default=1.0)
    args = ap.parse_args()

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
