#!/usr/bin/env python3
import os
import subprocess
import torch
import torchaudio as ta

os.environ["HF_HUB_OFFLINE"] = "1"

from chatterbox.tts import ChatterboxTTS

AUDIO_PROMPT_PATH = "/run/media/chadpenguin/Local Disk/projects(python env)/chatterbox/sample_from_script_1.ogg"
INPUT_VIDEO_PATH  = "/home/chadpenguin/Projects/AMAZON/raw_demo_video.mp4"
FINAL_VIDEO_PATH  = "/home/chadpenguin/Projects/AMAZON/final_voiced_video.mp4"
SUBTITLE_SRT_PATH = "/home/chadpenguin/Projects/AMAZON/subtitles.srt"
WORK_DIR          = "/home/chadpenguin/Projects/AMAZON/voiceover_work"
os.makedirs(WORK_DIR, exist_ok=True)

# Scene start times match generate_demo_video.py cumulative durations:
#   0.00 -> Scene 1 (12.56s)
#  12.56 -> Scene 2 (14.40s)
#  26.96 -> Scene 3 (12.96s)
#  39.92 -> Scene 4 (13.04s)
#  52.96 -> Scene 5 (11.20s)

SEGMENTS = [
    {
        "id": "clip_01",
        "start": 0.5,
        "text": (
            "When you connect conversational AI to physical smart locks... "
            "you run into a serious security problem. "
            "A visitor using social engineering or prompt injection can trick a standard language model "
            "into unlocking your door."
        ),
    },
    {
        "id": "clip_02",
        "start": 12.56,
        "text": (
            "SentryMesh puts a zero-trust airgap right in front of the deadbolt. "
            "AWS Strands Decider 2B sits between Alexa and the physical lock, "
            "evaluating every request in just 112 milliseconds without generating a single token."
        ),
    },
    {
        "id": "clip_03",
        "start": 26.96,
        "text": (
            "Watch an active prompt injection attack. "
            "The visitor tries to override our safety rules. "
            "Decider 2B flags the injection risk in 112 milliseconds, "
            "keeps the deadbolt locked, and immediately pushes a security alert to the living room Fire TV."
        ),
    },
    {
        "id": "clip_04",
        "start": 39.92,
        "text": (
            "Now a scheduled Amazon courier arrives. "
            "The driver scans their badge, "
            "Decider 2B confirms grounding in 112 milliseconds, "
            "unlocks the parcel drop, "
            "and Bedrock speaks a warm confirmation over the Ring doorbell."
        ),
    },
    {
        "id": "clip_05",
        "start": 52.96,
        "text": (
            "Across our full benchmark, Decider 2B was twelve times faster "
            "and four hundred times cheaper than relying on a language model alone, "
            "all while exposing a full Alexa-plus Streamable MCP server. "
            "Thanks for watching."
        ),
    },
]

# Subtitle text (shorter than voiceover for readability)
SUBTITLES = [
    "Connecting conversational AI to physical smart locks creates a serious security risk.",
    "SentryMesh adds a sub-120ms Strands Decider 2B reflex layer before physical locks.",
    "Strands Decider 2B stops prompt injection in 112ms and alerts Fire TV.",
    "Verified couriers are grounded in 112ms; Bedrock confirms entry via Ring audio.",
    "Decider 2B: 12x faster, 400x cheaper, with Alexa+ Streamable MCP.",
]


def fmt_srt(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = min(999, int(round((sec - int(sec)) * 1000)))
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def main():
    print("[1/5] Loading ChatterboxTTS on CUDA ...")
    model = ChatterboxTTS.from_pretrained(device="cuda")
    sr = model.sr

    clip_records = []
    print("[2/5] Synthesizing cloned voice clips ...")
    for seg, sub in zip(SEGMENTS, SUBTITLES):
        out_wav = os.path.join(WORK_DIR, f"{seg['id']}.wav")
        if not os.path.exists(out_wav):
            wav = model.generate(
                seg["text"],
                audio_prompt_path=AUDIO_PROMPT_PATH,
                cfg_weight=0.55,
                exaggeration=0.40,
                temperature=0.70,
                repetition_penalty=1.1,
            )
            ta.save(out_wav, wav, sr)
        wav, clip_sr = ta.load(out_wav)
        duration = wav.shape[1] / float(clip_sr)
        clip_records.append({
            "path":  out_wav,
            "start": seg["start"],
            "end":   seg["start"] + duration,
            "sub":   sub,
        })
        print(f"  -> {seg['id']} ({duration:.2f}s)")

    print("[3/5] Writing subtitles ...")
    srt_lines = []
    for i, rec in enumerate(clip_records, start=1):
        end_t = max(rec["end"], rec["start"] + 3.0)
        srt_lines.append(f"{i}\n{fmt_srt(rec['start'])} --> {fmt_srt(end_t)}\n{rec['sub']}\n")
    with open(SUBTITLE_SRT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))

    probe = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        INPUT_VIDEO_PATH
    ]).decode().strip()
    total_sec = float(probe)

    print(f"[4/5] Assembling master audio track ({total_sec:.1f}s) ...")
    total_samples = int(total_sec * sr)
    master = torch.zeros(1, total_samples, dtype=torch.float32)

    for rec in clip_records:
        wav, clip_sr = ta.load(rec["path"])
        if clip_sr != sr:
            wav = ta.transforms.Resample(clip_sr, sr)(wav)
        if wav.shape[0] > 1:
            wav = torch.mean(wav, dim=0, keepdim=True)
        s = int(rec["start"] * sr)
        e = min(s + wav.shape[1], total_samples)
        master[:, s:e] += wav[:, : e - s]

    peak = torch.max(torch.abs(master)).item()
    if peak > 0:
        master = master / peak * 0.94

    master_path = os.path.join(WORK_DIR, "master_track.wav")
    ta.save(master_path, master, sr)

    print("[5/5] Burning subtitles and muxing final video ...")
    sub_filter = (
        f"subtitles={SUBTITLE_SRT_PATH}:force_style="
        "'FontSize=18,FontName=Liberation Sans,Bold=1,"
        "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
        "Outline=1.8,Shadow=1.2,MarginV=26'"
    )
    subprocess.run([
        "ffmpeg", "-y",
        "-i", INPUT_VIDEO_PATH,
        "-i", master_path,
        "-vf", sub_filter,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        FINAL_VIDEO_PATH,
    ], check=True)
    print(f"[✓] Final video: {FINAL_VIDEO_PATH}")


if __name__ == "__main__":
    main()
