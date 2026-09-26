"""Add narration and English subtitles to the captured browser walkthrough.

Windows SAPI supplies offline narration. Optional tooling: ``imageio-ffmpeg`` and
``numpy``. The resulting MP4, VTT and transcript are committed README media.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
import wave
from pathlib import Path

import imageio_ffmpeg
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
MEDIA = ROOT / "docs" / "media"
TEXT = {
    "Overview": "RetailMind opens on observed M5 sales, with source limits visible.",
    "Analytics": "Explore sales by product, store, weekday and holiday.",
    "Forecast lab": "Choose a product and compare models on held-out dates.",
    "Measured forecast": "The selected model shows backtest error, future demand and an empirical band.",
    "Inventory": "No observed stock means no invented reorder quantity.",
    "Insights": "Insights explain what the observed sales support.",
    "Data studio": "Review source quality, missing fields and database tools.",
    "Reports": "Download sales, performance summaries and model evidence as CSV.",
}
FINAL_TEXT = "Real observations, auditable forecasts, clear limits."


def timestamp(seconds: float, *, vtt: bool = False) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, remaining = divmod(milliseconds, 3_600_000)
    minutes, remaining = divmod(remaining, 60_000)
    whole, fraction = divmod(remaining, 1000)
    return f"{hours:02}:{minutes:02}:{whole:02}{'.' if vtt else ','}{fraction:03}"


def main() -> None:
    manifest = json.loads((MEDIA / "capture-manifest.json").read_text(encoding="utf-8"))
    scenes = manifest["scenes"]
    assert len(scenes) >= 8 and scenes[0]["name"] == "Overview"
    first = float(scenes[0]["start"])
    duration = float(scenes[-1]["start"]) - first + 3.5
    cues = []
    for index, scene in enumerate(scenes):
        start = float(scene["start"]) - first + 0.35
        end = ((float(scenes[index + 1]["start"]) - first - 0.15) if index + 1 < len(scenes) else duration - 0.1)
        cues.append({"start": start, "end": end,
                     "text": FINAL_TEXT if index == len(scenes) - 1 else TEXT[scene["name"]]})
    (MEDIA / "transcript.md").write_text(
        "# RetailMind AI — walkthrough transcript\n\n"
        "Recorded from the running application with the bundled historical M5 subset. "
        "Forecast dates after 22 May 2016 are archival research estimates.\n\n"
        + "\n\n".join(f"**{timestamp(cue['start'], vtt=True)} — {scenes[index]['name']}**\n\n{cue['text']}"
                        for index, cue in enumerate(cues))
        + "\n\nThe UI uses observed M5 sales and prices. M5 contains no measured stock, unit cost, supplier or lead time, "
        "so the inventory page does not show a reorder amount.\n", encoding="utf-8")

    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    with tempfile.TemporaryDirectory(prefix="retailmind-narration-") as temporary:
        scratch = Path(temporary)
        cue_json = scratch / "cues.json"
        cue_json.write_text(json.dumps(cues, ensure_ascii=False), encoding="utf-8")
        subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File",
                        str(ROOT / "scripts" / "render_narration.ps1"), "-CueJson", str(cue_json),
                        "-OutputDirectory", str(scratch)], check=True)
        sample_rate = 22050
        mixed = np.zeros(int((duration + 0.5) * sample_rate), dtype=np.float32)
        for index, cue in enumerate(cues):
            path = scratch / f"cue-{index:02}.wav"
            with wave.open(str(path), "rb") as stream:
                assert stream.getframerate() == sample_rate and stream.getnchannels() == 1 and stream.getsampwidth() == 2
                signal = np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2").astype(np.float32) / 32768
            available = cue["end"] - cue["start"] - 0.08
            if len(signal) / sample_rate > available:
                sped = scratch / f"sped-{index:02}.wav"
                ratio = min(2.0, len(signal) / sample_rate / available + 0.03)
                subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(path),
                                "-filter:a", f"atempo={ratio:.3f}", "-ar", str(sample_rate), "-ac", "1", str(sped)], check=True)
                with wave.open(str(sped), "rb") as stream:
                    signal = np.frombuffer(stream.readframes(stream.getnframes()), dtype="<i2").astype(np.float32) / 32768
            cue["caption_end"] = min(cue["end"], cue["start"] + len(signal) / sample_rate + 0.25)
            offset = int(cue["start"] * sample_rate)
            end = min(offset + len(signal), len(mixed))
            mixed[offset:end] += signal[:end - offset]
        peak = max(float(np.abs(mixed).max()), 1.0)
        audio = scratch / "narration.wav"
        with wave.open(str(audio), "wb") as stream:
            stream.setnchannels(1)
            stream.setsampwidth(2)
            stream.setframerate(sample_rate)
            stream.writeframes((np.clip(mixed / peak, -1, 1) * 32767).astype("<i2").tobytes())
        (MEDIA / "walkthrough.vtt").write_text("WEBVTT\n\n" + "\n\n".join(
            f"{timestamp(cue['start'], vtt=True)} --> {timestamp(cue['caption_end'], vtt=True)}\n{cue['text']}"
            for cue in cues) + "\n", encoding="utf-8")
        (MEDIA / "walkthrough.srt").write_text("\n\n".join(
            f"{index + 1}\n{timestamp(cue['start'])} --> {timestamp(cue['caption_end'])}\n{cue['text']}"
            for index, cue in enumerate(cues)) + "\n", encoding="utf-8")
        style = "FontName=Arial,FontSize=11,PrimaryColour=&H00FFFFFF,OutlineColour=&H990A1728,BorderStyle=1,Outline=2,Shadow=0,MarginV=13"
        output = MEDIA / "walkthrough.mp4"
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-ss", str(first),
                        "-i", str(MEDIA / "walkthrough.webm"), "-i", str(audio), "-t", str(duration),
                        "-vf", f"subtitles=docs/media/walkthrough.srt:force_style='{style}'",
                        "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
                        "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", "-shortest",
                        "-metadata", "title=RetailMind AI working application walkthrough", str(output)],
                       cwd=ROOT, check=True)
    print(f"{output} ({duration:.1f} seconds, narrated and captioned)")


if __name__ == "__main__":
    main()
