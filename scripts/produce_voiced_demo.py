#!/usr/bin/env python3
import os
import subprocess
import time
import torch
import torchaudio as ta

os.environ["HF_HUB_OFFLINE"] = "1"

from chatterbox.tts import ChatterboxTTS

# --- Configurations ---
AUDIO_PROMPT_PATH = "/run/media/chadpenguin/Local Disk/projects(python env)/chatterbox/sample_from_script_1.ogg"
INPUT_VIDEO_PATH = "/home/chadpenguin/Projects/AMAZON/raw_demo_video.mp4"
FINAL_VIDEO_PATH = "/home/chadpenguin/Projects/AMAZON/final_voiced_video.mp4"
SUBTITLE_SRT_PATH = "/home/chadpenguin/Projects/AMAZON/subtitles.srt"
WORK_DIR = "/home/chadpenguin/Projects/AMAZON/voiceover_work"
os.makedirs(WORK_DIR, exist_ok=True)

# Timed dialogue segments (start time in seconds)
SEGMENTS = [
    {
        "id": "clip_01",
        "start": 0.8,
        "text": "When you connect conversational AI to physical smart locks... you run into a serious security dilemma. If a visitor tries social engineering or prompt injection... a standard language model can easily get tricked into unlocking.",
        "sub": "Connecting conversational AI to physical smart locks creates a serious security risk."
    },
    {
        "id": "clip_02",
        "start": 16.0,
        "text": "We built SentryMesh to introduce a zero-trust physical-to-digital airgap. Right in front of our deadbolt... we placed AWS Strands Decider 2B as a non-generative reflex layer... evaluating security in just 112 milliseconds.",
        "sub": "SentryMesh adds a sub-120ms Strands Decider 2B reflex layer before physical locks."
    },
    {
        "id": "clip_03",
        "start": 32.5,
        "text": "Watch what happens during an active prompt injection attack. A visitor tries to override security rules... Decider 2B flags the injection risk in 112 milliseconds... keeps the physical deadbolt locked... and pushes an alert to the living room Fire TV.",
        "sub": "Strands Decider 2B stops prompt injection in 112ms and alerts Fire TV."
    },
    {
        "id": "clip_04",
        "start": 49.5,
        "text": "Now watch a scheduled courier arrive with an Amazon package. A driver scans their badge... Decider 2B verifies grounding in 112 milliseconds... unlocks the parcel drop... and Amazon Bedrock speaks a warm confirmation over the Ring doorbell.",
        "sub": "Verified couriers are grounded in 112ms; Bedrock confirms entry via Ring audio."
    },
    {
        "id": "clip_05",
        "start": 65.5,
        "text": "Across our benchmark... Decider 2B was 12 times faster and 400 times cheaper than relying on an LLM alone... all while exposing an Alexa+ Streamable MCP server. Thanks for watching.",
        "sub": "Decider 2B: 12x faster, 400x cheaper, with Alexa+ Streamable MCP."
    }
]


def format_srt_time(sec):
    hrs = int(sec // 3600)
    mins = int((sec % 3600) // 60)
    secs = int(sec % 60)
    millis = int(round((sec - int(sec)) * 1000))
    if millis >= 1000:
        millis = 999
    return f"{hrs:02d}:{mins:02d}:{secs:02d},{millis:03d}"


def main():
    # 1. Load ChatterboxTTS onto GPU
    print("[1/5] Loading ChatterboxTTS on CUDA...")
    model = ChatterboxTTS.from_pretrained(device="cuda")
    sr = model.sr

    # 2. Synthesize each segment
    clip_records = []
    print("[2/5] Synthesizing authentic cloned speech clips...")
    for idx, seg in enumerate(SEGMENTS, start=1):
        out_wav = os.path.join(WORK_DIR, f"{seg['id']}.wav")
        wav = model.generate(
            seg["text"],
            audio_prompt_path=AUDIO_PROMPT_PATH,
            cfg_weight=0.55,
            exaggeration=0.40,
            temperature=0.70,
            repetition_penalty=1.1,
        )
        ta.save(out_wav, wav, sr)
        duration = wav.shape[1] / float(sr)

        clip_records.append({
            "path": out_wav,
            "start": seg["start"],
            "end": seg["start"] + duration,
            "sub": seg["sub"]
        })
        print(f"  -> Generated {seg['id']} ({duration:.2f}s)")

    # 3. Create .srt Subtitle File
    print("[3/5] Generating Subtitles...")
    srt_lines = []
    for idx, rec in enumerate(clip_records, start=1):
        s_time = format_srt_time(rec["start"])
        e_time = format_srt_time(max(rec["end"], rec["start"] + 3.0))
        srt_lines.append(f"{idx}\n{s_time} --> {e_time}\n{rec['sub']}\n")

    with open(SUBTITLE_SRT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))

    # 4. Measure video duration
    probe_cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        INPUT_VIDEO_PATH
    ]
    try:
        video_dur_str = subprocess.check_output(probe_cmd).decode().strip()
        total_duration_sec = float(video_dur_str)
    except Exception:
        total_duration_sec = 82.0

    print(f"[4/5] Assembling master audio track ({total_duration_sec:.1f}s)...")
    total_samples = int(total_duration_sec * sr)
    master_audio = torch.zeros(1, total_samples, dtype=torch.float32)

    for rec in clip_records:
        wav, clip_sr = ta.load(rec["path"])
        if clip_sr != sr:
            resampler = ta.transforms.Resample(orig_freq=clip_sr, new_freq=sr)
            wav = resampler(wav)
        if wav.shape[0] > 1:
            wav = torch.mean(wav, dim=0, keepdim=True)

        start_sample = int(rec["start"] * sr)
        end_sample = min(start_sample + wav.shape[1], total_samples)
        clip_samples = end_sample - start_sample
        master_audio[:, start_sample:end_sample] += wav[:, :clip_samples]

    # Peak normalization
    max_val = torch.max(torch.abs(master_audio)).item()
    if max_val > 0:
        master_audio = (master_audio / max_val) * 0.94

    master_wav_path = os.path.join(WORK_DIR, "master_track.wav")
    ta.save(master_wav_path, master_audio, sr)

    # 5. Burn subtitles & mux with FFmpeg
    print("[5/5] Burning subtitles and muxing into final video...")
    sub_filter = (
        f"subtitles={SUBTITLE_SRT_PATH}:force_style="
        "'FontSize=16,FontName=Liberation Sans,Bold=1,PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,Outline=1.6,Shadow=1.0,MarginV=22'"
    )
    ffmpeg_cmd = [
        "ffmpeg", "-y",
        "-i", INPUT_VIDEO_PATH,
        "-i", master_wav_path,
        "-vf", sub_filter,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "19",
        "-c:a", "aac",
        "-b:a", "192k",
        "-shortest",
        FINAL_VIDEO_PATH
    ]
    subprocess.run(ffmpeg_cmd, check=True)
    print(f"[✓] Final Video Created Successfully: {FINAL_VIDEO_PATH}")


if __name__ == "__main__":
    main()
