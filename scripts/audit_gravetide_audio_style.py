#!/usr/bin/env python3
"""Measure every relevant shipped Gravetide audio reference before authoring."""

from __future__ import annotations

import argparse
import io
import json
import math
import sys
import wave
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_AUDIT_ROOT = ROOT.parent / ".tmp/gravetide-vanilla-audio-audit"
DEFAULT_FSB5_ROOT = ROOT.parent / ".tmp/audio-audit-tools/python-fsb5"
DEFAULT_OUTPUT = ROOT / "build/style_audit/gravetide_audio_metrics.json"


def dbfs(value: float) -> float:
    return -120.0 if value <= 1e-12 else 20.0 * math.log10(value)


def decode_ogg(blob: bytes) -> tuple[np.ndarray, int]:
    import av

    chunks: list[np.ndarray] = []
    rate = 0
    with av.open(io.BytesIO(blob), format="ogg") as container:
        for frame in container.decode(audio=0):
            rate = int(frame.sample_rate)
            samples = frame.to_ndarray()
            if np.issubdtype(samples.dtype, np.integer):
                limit = float(max(abs(np.iinfo(samples.dtype).min), np.iinfo(samples.dtype).max))
                samples = samples.astype(np.float32) / limit
            else:
                samples = samples.astype(np.float32, copy=False)
            if samples.ndim == 1:
                samples = samples[np.newaxis, :]
            chunks.append(samples.T)
    if not chunks or rate <= 0:
        raise RuntimeError("Decoded OGG contains no PCM frames")
    return np.concatenate(chunks, axis=0), rate


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path), "rb") as source:
        if source.getsampwidth() != 2:
            raise RuntimeError(f"Expected PCM16 WAV: {path}")
        channels = source.getnchannels()
        rate = source.getframerate()
        pcm = np.frombuffer(source.readframes(source.getnframes()), dtype="<i2")
    return pcm.reshape(-1, channels).astype(np.float32) / 32768.0, rate


def waveform_metrics(samples: np.ndarray, rate: int) -> dict[str, float | int]:
    if samples.ndim == 1:
        samples = samples[:, np.newaxis]
    mono = samples.mean(axis=1, dtype=np.float64)
    peak = float(np.max(np.abs(samples)))
    rms = float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))

    envelope_window = max(1, round(rate * 0.02))
    usable = len(mono) - (len(mono) % envelope_window)
    envelope = np.sqrt(
        np.mean(
            mono[:usable].reshape(-1, envelope_window) ** 2,
            axis=1,
        )
    )
    envelope_db = 20.0 * np.log10(np.maximum(envelope, 1e-9))
    threshold = float(np.percentile(envelope, 85.0))
    transient_count = int(
        np.count_nonzero(
            (envelope[1:-1] > envelope[:-2])
            & (envelope[1:-1] >= envelope[2:])
            & (envelope[1:-1] > threshold)
        )
    )

    fft_size = 4096
    if len(mono) < fft_size:
        padded = np.pad(mono, (0, fft_size - len(mono)))
        windows = padded[np.newaxis, :]
    else:
        starts = np.linspace(0, len(mono) - fft_size, num=min(128, len(mono) // fft_size), dtype=int)
        windows = np.stack([mono[start : start + fft_size] for start in starts])
    windows *= np.hanning(fft_size)[np.newaxis, :]
    spectrum = np.mean(np.abs(np.fft.rfft(windows, axis=1)) ** 2, axis=0)
    frequencies = np.fft.rfftfreq(fft_size, 1.0 / rate)
    total_power = float(np.sum(spectrum)) or 1.0

    def band_share(low: float, high: float) -> float:
        mask = (frequencies >= low) & (frequencies < high)
        return float(np.sum(spectrum[mask]) / total_power)

    centroid = float(np.sum(frequencies * spectrum) / total_power)
    duration = len(samples) / rate
    seam_length = min(len(samples) // 2, round(rate * 0.05))
    seam = samples[:seam_length] - samples[-seam_length:]
    seam_rms = float(np.sqrt(np.mean(np.square(seam, dtype=np.float64))))
    stereo_correlation = 1.0
    if samples.shape[1] >= 2:
        left = samples[:, 0].astype(np.float64)
        right = samples[:, 1].astype(np.float64)
        denominator = float(np.sqrt(np.dot(left, left) * np.dot(right, right)))
        stereo_correlation = 0.0 if denominator <= 1e-12 else float(np.dot(left, right) / denominator)

    return {
        "sample_rate": rate,
        "channels": int(samples.shape[1]),
        "duration_seconds": round(duration, 4),
        "peak_dbfs": round(dbfs(peak), 3),
        "rms_dbfs": round(dbfs(rms), 3),
        "crest_db": round(dbfs(peak) - dbfs(rms), 3),
        "dynamic_range_db": round(float(np.percentile(envelope_db, 95) - np.percentile(envelope_db, 20)), 3),
        "transients_per_minute": round(transient_count * 60.0 / max(duration, 1e-6), 3),
        "spectral_centroid_hz": round(centroid, 2),
        "sub_share_20_120": round(band_share(20.0, 120.0), 5),
        "low_mid_share_120_500": round(band_share(120.0, 500.0), 5),
        "mid_share_500_2000": round(band_share(500.0, 2000.0), 5),
        "high_share_2000_8000": round(band_share(2000.0, 8000.0), 5),
        "air_share_8000_plus": round(band_share(8000.0, rate / 2.0 + 1.0), 5),
        "stereo_correlation": round(stereo_correlation, 5),
        "loop_seam_rms_dbfs": round(dbfs(seam_rms), 3),
    }


def import_fsb5(tool_root: Path):
    sys.path.insert(0, str(tool_root))
    import fsb5  # type: ignore[import-not-found]

    return fsb5


def fsb_metadata(fsb) -> list[dict[str, object]]:
    return [
        {
            "index": index,
            "name": sample.name,
            "sample_rate": sample.frequency,
            "channels": sample.channels,
            "frames": sample.samples,
            "duration_seconds": round(sample.samples / sample.frequency, 4),
        }
        for index, sample in enumerate(fsb.samples)
    ]


def validate_outputs(outputs: dict[str, dict[str, float | int]]) -> None:
    errors: list[str] = []
    music_path = "music/gravetide_slug/gravetide_slug_boss_theme.wav"
    music = outputs.get(music_path)
    if music is None:
        errors.append(f"missing {music_path}")
    else:
        music_ranges = {
            "duration_seconds": (149.9, 150.1),
            "rms_dbfs": (-25.5, -21.5),
            "crest_db": (15.0, 26.0),
            "dynamic_range_db": (7.0, 18.0),
            "spectral_centroid_hz": (400.0, 1_200.0),
            "sub_share_20_120": (0.0, 0.15),
            "mid_share_500_2000": (0.20, 0.70),
            "high_share_2000_8000": (0.01, 0.15),
            "stereo_correlation": (-0.1, 0.75),
        }
        for key, (low, high) in music_ranges.items():
            value = float(music[key])
            if not low <= value <= high:
                errors.append(f"music {key}={value} outside [{low}, {high}]")
        if music["sample_rate"] != 48_000 or music["channels"] != 2:
            errors.append("music must be 48 kHz stereo")

    duration_ranges = {
        "attack_light": (2.0, 2.2),
        "attack-": (1.7, 1.95),
        "hurt-": (0.7, 0.9),
        "die-": (2.15, 2.4),
        "devour_end": (1.9, 2.2),
        "devour-": (1.15, 1.35),
    }
    sfx_outputs = {
        path: metrics for path, metrics in outputs.items() if path.startswith("sfx/")
    }
    if len(sfx_outputs) != 15:
        errors.append(f"expected 15 Gravetide SFX files, found {len(sfx_outputs)}")
    for path, metrics in sfx_outputs.items():
        duration_range = next(
            (limits for token, limits in duration_ranges.items() if token in path),
            None,
        )
        if duration_range is None:
            errors.append(f"unclassified SFX output: {path}")
            continue
        duration = float(metrics["duration_seconds"])
        if not duration_range[0] <= duration <= duration_range[1]:
            errors.append(f"{path} duration={duration} outside {duration_range}")
        checks = {
            "rms_dbfs": (-41.0, -26.0),
            "crest_db": (12.0, 26.0),
            "spectral_centroid_hz": (600.0, 1_800.0),
            "sub_share_20_120": (0.0, 0.08),
            "mid_share_500_2000": (0.25, 0.85),
            "high_share_2000_8000": (0.03, 0.30),
            "stereo_correlation": (0.35, 0.95),
        }
        for key, (low, high) in checks.items():
            value = float(metrics[key])
            if not low <= value <= high:
                errors.append(f"{path} {key}={value} outside [{low}, {high}]")
        if metrics["sample_rate"] != 48_000 or metrics["channels"] != 2:
            errors.append(f"{path} must be 48 kHz stereo")

    if errors:
        raise RuntimeError("Gravetide audio output gate failed:\n  " + "\n  ".join(errors))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-root", type=Path, default=DEFAULT_AUDIT_ROOT)
    parser.add_argument("--fsb5-root", type=Path, default=DEFAULT_FSB5_ROOT)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--outputs-only",
        action="store_true",
        help="Skip shipped FSB decoding and validate only generated WAV outputs.",
    )
    args = parser.parse_args()

    report: dict[str, object] = {
        "source": "Slay the Spire 2 v0.109.0 shipped FMOD banks",
        "inventory": {},
        "underdocks_boss_music": {},
        "corpse_slug_sfx": {},
        "gravetide_outputs": {},
    }

    music_metrics = report["underdocks_boss_music"]
    sfx_metrics = report["corpse_slug_sfx"]
    if not args.outputs_only:
        fsb5 = import_fsb5(args.fsb5_root.resolve())
        act1_fsb = fsb5.load((args.audit_root / "act1_b1.fsb").read_bytes())
        sfx_fsb = fsb5.load((args.audit_root / "sfx.fsb").read_bytes())
        report["inventory"] = {
            "act1_b1": fsb_metadata(act1_fsb),
            "sfx_sample_count": len(sfx_fsb.samples),
        }
        for sample in act1_fsb.samples:
            if "WaterfallGiant" not in sample.name and "SoulFysh" not in sample.name:
                continue
            pcm, rate = decode_ogg(act1_fsb.rebuild_sample(sample))
            music_metrics[sample.name] = waveform_metrics(pcm, rate)
        for sample in sfx_fsb.samples:
            if "corpse_slug" not in sample.name.lower():
                continue
            pcm, rate = decode_ogg(sfx_fsb.rebuild_sample(sample))
            sfx_metrics[sample.name] = waveform_metrics(pcm, rate)

    output_metrics = report["gravetide_outputs"]
    for path in [
        ROOT / "music/gravetide_slug/gravetide_slug_boss_theme.wav",
        *sorted((ROOT / "sfx/gravetide_slug").glob("*.wav")),
    ]:
        pcm, rate = read_wav(path)
        output_metrics[path.relative_to(ROOT).as_posix()] = waveform_metrics(pcm, rate)

    validate_outputs(output_metrics)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(
        "GRAVETIDE_AUDIO_STYLE_AUDIT_PASS "
        f"music={len(music_metrics)} corpse_slug_sfx={len(sfx_metrics)} "
        f"outputs={len(output_metrics)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
