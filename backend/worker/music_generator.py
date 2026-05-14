"""
music_generator.py — Generates royalty-free ambient background music using numpy.

Produces 4 moods as 60-second WAV loops:
  ambient-calm     : slow pad, finance/lifestyle topics
  ambient-tech     : pulsing drone, tech/crypto/AI topics
  ambient-dramatic : tension build, war/news/politics topics
  ambient-upbeat   : bright arp, comparison/product topics

All synthesis is done with numpy; no external audio files needed.
"""
import asyncio
import math
from pathlib import Path

import numpy as np

SAMPLE_RATE = 44100
DURATION = 60  # seconds per loop
_TRACKS: dict[str, dict] = {
    "ambient-calm.wav": {
        "label": "Ambient Calm",
        "desc": "Slow pad — finance, lifestyle, savings",
        "mood": "calm",
    },
    "ambient-tech.wav": {
        "label": "Ambient Tech",
        "desc": "Pulsing drone — tech, crypto, AI",
        "mood": "tech",
    },
    "ambient-dramatic.wav": {
        "label": "Ambient Dramatic",
        "desc": "Tension build — war, news, politics",
        "mood": "dramatic",
    },
    "ambient-upbeat.wav": {
        "label": "Ambient Upbeat",
        "desc": "Bright arpeggio — comparisons, products",
        "mood": "upbeat",
    },
}


# ---------------------------------------------------------------------------
# Low-level synthesis helpers
# ---------------------------------------------------------------------------

def _t(n_samples: int) -> np.ndarray:
    return np.linspace(0, DURATION, n_samples, endpoint=False)


def _sine(freq: float, t: np.ndarray, phase: float = 0.0) -> np.ndarray:
    return np.sin(2 * math.pi * freq * t + phase)


def _adsr(n: int, a: float, d: float, s_level: float, r: float) -> np.ndarray:
    """Simple ADSR envelope (fractions of total length)."""
    env = np.zeros(n)
    ai = int(a * n); di = int(d * n); ri = int(r * n)
    si = n - ai - di - ri
    if ai > 0:
        env[:ai] = np.linspace(0, 1, ai)
    if di > 0:
        env[ai:ai+di] = np.linspace(1, s_level, di)
    if si > 0:
        env[ai+di:ai+di+si] = s_level
    if ri > 0:
        env[ai+di+si:] = np.linspace(s_level, 0, ri)
    return env


def _lfo(rate: float, t: np.ndarray, depth: float = 1.0, offset: float = 0.0) -> np.ndarray:
    return offset + depth * (0.5 + 0.5 * np.sin(2 * math.pi * rate * t))


def _soft_clip(x: np.ndarray) -> np.ndarray:
    return np.tanh(x) * 0.9


def _fade_edges(x: np.ndarray, fade_ms: int = 80) -> np.ndarray:
    fade_n = int(SAMPLE_RATE * fade_ms / 1000)
    if len(x) > fade_n * 2:
        x[:fade_n] *= np.linspace(0, 1, fade_n)
        x[-fade_n:] *= np.linspace(1, 0, fade_n)
    return x


# ---------------------------------------------------------------------------
# Track generators
# ---------------------------------------------------------------------------

def _gen_calm(n: int, t: np.ndarray) -> np.ndarray:
    """Slow detuned pad — C major: C2, G2, E3, C4."""
    freqs = [65.41, 98.00, 164.81, 261.63]
    detune = [0.0, 0.3, -0.2, 0.15]

    lfo1 = _lfo(0.07, t, depth=0.25, offset=0.75)  # slow volume swell
    lfo2 = _lfo(0.13, t, depth=0.15, offset=0.85)

    mix = np.zeros(n)
    for f, d in zip(freqs, detune):
        wave = _sine(f + d, t) * 0.55
        wave += _sine(f * 2 + d * 0.5, t) * 0.15   # 2nd harmonic
        mix += wave

    mix *= lfo1 * lfo2
    # Add gentle reverb tail via comb filter approximation
    delay_n = int(SAMPLE_RATE * 0.35)
    if delay_n < n:
        mix[delay_n:] += mix[:-delay_n] * 0.22
    return mix


def _gen_tech(n: int, t: np.ndarray) -> np.ndarray:
    """Pulsing electronic drone — Am: A1, E2, A2, C3, E3."""
    freqs = [55.0, 82.41, 110.0, 130.81, 164.81]
    detune = [0.0, 0.5, -0.3, 0.2, -0.4]

    # Rhythmic pulse LFO at ~120 BPM quarter note
    pulse = _lfo(2.0, t, depth=0.40, offset=0.60)
    # Slow filter-like sweep
    sweep = _lfo(0.05, t, depth=0.30, offset=0.70)

    mix = np.zeros(n)
    for f, d in zip(freqs, detune):
        wave = _sine(f + d, t) * 0.50
        # Add subtle odd harmonics for grit
        wave += _sine(f * 3 + d, t) * 0.08
        wave += _sine(f * 5 + d, t) * 0.04
        mix += wave

    mix *= pulse * sweep
    # High-frequency shimmer
    shimmer = _sine(2093.0, t) * 0.03 * _lfo(0.5, t, depth=0.8, offset=0.2)
    mix += shimmer
    return mix


def _gen_dramatic(n: int, t: np.ndarray) -> np.ndarray:
    """Tension build — low rumble, minor 2nds, slow crescendo."""
    # Cm: C2, Eb2, G2 + sub-bass rumble
    freqs = [65.41, 77.78, 98.00]
    detune = [0.0, -0.4, 0.3]

    # Slow crescendo envelope over full 60s
    crescendo = np.linspace(0.3, 1.0, n) ** 1.5
    # Tremolo
    tremolo = _lfo(3.5, t, depth=0.15, offset=0.85)

    mix = np.zeros(n)
    for f, d in zip(freqs, detune):
        wave = _sine(f + d, t) * 0.55
        # Second harmonic adds richness
        wave += _sine(f * 2 + d, t) * 0.20
        mix += wave

    # Sub bass
    sub = _sine(32.7, t) * 0.35 * crescendo
    mix += sub
    mix *= crescendo * tremolo

    # Occasional low thud (every ~8 bars ≈ 16s at slow tempo)
    for onset in [0, 16, 32, 48]:
        start = int(onset * SAMPLE_RATE)
        end = min(start + int(SAMPLE_RATE * 0.4), n)
        attack_n = end - start
        if attack_n > 0:
            imp = _sine(60.0, t[start:end]) * np.linspace(0.5, 0, attack_n)
            mix[start:end] += imp * 0.25

    return mix


def _gen_upbeat(n: int, t: np.ndarray) -> np.ndarray:
    """Bright arpeggio — G major: G4, B4, D5, G5 at 100 BPM 8ths."""
    arp_freqs = [392.00, 493.88, 587.33, 784.00]  # G4 B4 D5 G5
    bpm = 100.0
    step_dur = 60.0 / bpm / 2  # 8th notes

    # Backing pad: G major chord G2+D3+B3
    pad_freqs = [98.00, 146.83, 246.94]
    pad_lfo = _lfo(0.12, t, depth=0.20, offset=0.80)

    pad = np.zeros(n)
    for f in pad_freqs:
        pad += _sine(f, t) * 0.25
    pad *= pad_lfo

    # Arpeggio: each note fires for step_dur, cycling through arp_freqs
    arp = np.zeros(n)
    arp_idx = 0
    step_n = int(step_dur * SAMPLE_RATE)
    pos = 0
    while pos < n:
        end = min(pos + step_n, n)
        block_len = end - pos
        t_block = t[pos:end]
        freq = arp_freqs[arp_idx % len(arp_freqs)]
        env = np.linspace(1, 0, block_len) ** 0.5
        note = _sine(freq, t_block, phase=0.0) * 0.18 * env
        # Slight pluck character
        note += _sine(freq * 2, t_block) * 0.04 * env
        arp[pos:end] += note
        pos += step_n
        arp_idx += 1

    # Volume swing — emphasise every 4th step (downbeat)
    beat_n = step_n * 4
    swing = np.ones(n)
    for b in range(0, n, beat_n):
        accent_end = min(b + step_n, n)
        if accent_end > b:
            swing[b:accent_end] = np.linspace(1.5, 1.0, accent_end - b)
    arp *= swing

    return pad + arp


# ---------------------------------------------------------------------------
# WAV writer (no external deps)
# ---------------------------------------------------------------------------

def _write_wav(path: Path, samples: np.ndarray) -> None:
    """Write mono float32 samples as 16-bit WAV."""
    import struct
    samples = _soft_clip(samples)
    samples = _fade_edges(samples)
    # Normalize to 85% full scale
    peak = np.max(np.abs(samples))
    if peak > 0:
        samples = samples / peak * 0.85
    pcm = (samples * 32767).astype(np.int16)
    data = pcm.tobytes()

    n_samples = len(pcm)
    n_channels = 1
    bits = 16
    byte_rate = SAMPLE_RATE * n_channels * bits // 8
    block_align = n_channels * bits // 8
    data_size = len(data)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + data_size, b"WAVE",
        b"fmt ", 16, 1, n_channels, SAMPLE_RATE,
        byte_rate, block_align, bits,
        b"data", data_size,
    )
    path.write_bytes(header + data)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_GENERATORS = {
    "calm":     _gen_calm,
    "tech":     _gen_tech,
    "dramatic": _gen_dramatic,
    "upbeat":   _gen_upbeat,
}


def generate_preset_tracks(music_dir: Path) -> list[dict]:
    """
    Generate all 4 preset background music tracks into music_dir.
    Skips tracks that already exist. Returns list of generated track metadata.
    """
    music_dir.mkdir(parents=True, exist_ok=True)
    n = SAMPLE_RATE * DURATION
    t = _t(n)
    generated = []

    for filename, meta in _TRACKS.items():
        dest = music_dir / filename
        if dest.exists() and dest.stat().st_size > 10_000:
            generated.append({"name": filename, "path": str(dest), **meta, "status": "exists"})
            continue
        mood = meta["mood"]
        gen_fn = _GENERATORS[mood]
        samples = gen_fn(n, t)
        _write_wav(dest, samples)
        size_mb = round(dest.stat().st_size / 1024 / 1024, 1)
        print(f"[music] generated {filename} ({size_mb} MB)")
        generated.append({"name": filename, "path": str(dest), **meta,
                           "size_mb": size_mb, "status": "generated"})

    return generated


async def generate_preset_tracks_async(music_dir: Path) -> list[dict]:
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, generate_preset_tracks, music_dir)


# Mood → track filename mapping for auto-selection in pipeline
MOOD_TRACK: dict[str, str] = {
    "finance":   "ambient-calm.wav",
    "crypto":    "ambient-tech.wav",
    "tech":      "ambient-tech.wav",
    "ai":        "ambient-tech.wav",
    "war":       "ambient-dramatic.wav",
    "politics":  "ambient-dramatic.wav",
    "news":      "ambient-dramatic.wav",
    "health":    "ambient-calm.wav",
    "food":      "ambient-upbeat.wav",
    "travel":    "ambient-upbeat.wav",
    "sport":     "ambient-upbeat.wav",
    "education": "ambient-calm.wav",
    "generic":   "ambient-tech.wav",
}
