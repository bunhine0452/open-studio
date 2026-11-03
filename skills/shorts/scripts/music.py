"""배경음악 — numpy 로 합성한 짧은 반복곡. 음원 파일·저작권·구독이 없다.

스타일
  pop    밝은 4박 킥 + 엇박 하이햇 + 베이스 + 짧게 튕기는 화음 (쇼핑·제품 소개)
  chill  부드러운 킥·스네어 + 전자 피아노 화음 + 옅은 잡음 (요리·생활·차분한 정보)
  tech   16분음 아르페지오 + 낮은 신스 베이스 (전자제품·AI)
화음 진행은 I–V–vi–IV (스타일마다 조를 바꾼다). 목소리가 나오는 동안 자동으로 소리를 줄인다(덕킹).
"""
from __future__ import annotations

import numpy as np

SR = 48000
KEYS = {"pop": 60, "chill": 57, "tech": 62}  # 으뜸음 MIDI (C4·A3·D4)
PROG = [(0, 4, 7), (7, 11, 14), (9, 12, 16), (5, 9, 12)]  # I V vi IV


def hz(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def env(n, a=0.005, d=0.2):
    t = np.arange(n) / SR
    return np.minimum(t / a, 1) * np.exp(-t / d)


def kick(n, soft=False):
    t = np.arange(n) / SR
    f = 50 + (110 if not soft else 70) * np.exp(-t / 0.035)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * env(n, 0.001, 0.18 if not soft else 0.12)


def hat(n, rng, open_=False):
    x = rng.standard_normal(n)
    x = np.diff(x, prepend=0)  # 밝게
    return x * env(n, 0.0008, 0.06 if open_ else 0.018) * 0.35


def snare(n, rng):
    t = np.arange(n) / SR
    return (rng.standard_normal(n) * 0.5 + np.sin(2 * np.pi * 190 * t) * 0.5) * env(n, 0.001, 0.09)


def tone(freq, n, kind="pluck"):
    t = np.arange(n) / SR
    if kind == "pluck":  # 짧은 사각+사인 섞인 튕김
        w = 0.6 * np.sin(2 * np.pi * freq * t) + 0.25 * np.sign(np.sin(2 * np.pi * freq * t)) * 0.4
        return w * env(n, 0.003, 0.12)
    if kind == "ep":  # 전자 피아노: 배음 둘 + 느린 감쇠 + 살짝 떨림
        vib = 1 + 0.003 * np.sin(2 * np.pi * 5 * t)
        w = np.sin(2 * np.pi * freq * vib * t) + 0.3 * np.sin(2 * np.pi * 2 * freq * t) * np.exp(-t / 0.3)
        return w * env(n, 0.01, 0.9) * 0.5
    if kind == "bass":
        w = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * 2 * freq * t)
        return w * env(n, 0.005, 0.35)
    if kind == "saw":
        ph = (freq * t) % 1.0
        return (2 * ph - 1) * env(n, 0.002, 0.09) * 0.5
    raise ValueError(kind)


def loop(style="pop", bpm=None, bars=4, seed=3) -> np.ndarray:
    """한 바퀴(4마디) 반복곡."""
    rng = np.random.default_rng(seed)
    bpm = bpm or {"pop": 116, "chill": 84, "tech": 124}[style]
    beat = 60 / bpm
    n = int(bars * 4 * beat * SR)
    out = np.zeros(n)
    root = KEYS[style]

    def put(x, t):
        i = int(t * SR)
        j = min(n, i + len(x))
        if i < n:
            out[i:j] += x[: j - i]

    for bar in range(bars):
        chord = PROG[bar % 4]
        t0 = bar * 4 * beat
        for b in range(4):
            tb = t0 + b * beat
            if style == "pop":
                put(kick(int(0.35 * SR)) * 0.9, tb)
                put(hat(int(0.08 * SR), rng) , tb + beat / 2)
                put(tone(hz(root - 24 + chord[0]), int(beat * SR), "bass") * 0.5, tb)
                if b % 2 == 1:
                    put(snare(int(0.2 * SR), rng) * 0.35, tb)
                for k, iv in enumerate(chord):  # 엇박 화음 튕김
                    put(tone(hz(root + iv), int(0.25 * SR), "pluck") * 0.16, tb + beat / 2 + k * 0.006)
            elif style == "chill":
                if b in (0, 2):
                    put(kick(int(0.3 * SR), soft=True) * 0.7, tb)
                if b in (1, 3):
                    put(snare(int(0.18 * SR), rng) * 0.22, tb)
                put(hat(int(0.05 * SR), rng) * 0.45, tb + beat / 2)
                if b == 0:
                    for k, iv in enumerate(chord):
                        put(tone(hz(root + iv), int(4 * beat * SR), "ep") * 0.22, tb + k * 0.02)
                    put(tone(hz(root - 24 + chord[0]), int(2 * beat * SR), "bass") * 0.45, tb)
                if b == 2:
                    put(tone(hz(root - 24 + chord[0]), int(2 * beat * SR), "bass") * 0.45, tb)
            elif style == "tech":
                put(kick(int(0.3 * SR)) * 0.85, tb)
                put(hat(int(0.06 * SR), rng) * 0.8, tb + beat / 2)
                for s in range(4):  # 16분음 아르페지오
                    iv = chord[(b * 4 + s) % 3] + (12 if s == 3 else 0)
                    put(tone(hz(root + iv), int(beat / 4 * SR), "saw") * 0.14, tb + s * beat / 4)
                put(tone(hz(root - 24 + chord[0]), int(beat * SR), "bass") * 0.5, tb)
    if style == "chill":
        out += rng.standard_normal(n) * 0.004  # 옅은 레코드 잡음
    return out / max(1e-6, np.abs(out).max())


def bed(total: float, style="pop", bpm=None, gain_db=-14.0, voice=None, duck_db=8.0, fade=1.2) -> np.ndarray:
    """total 초 길이로 반복곡을 이어 붙이고, voice(같은 길이 배열)가 있으면 말하는 동안 duck_db 만큼 줄인다."""
    one = loop(style, bpm)
    n = int(total * SR)
    reps = int(np.ceil(n / len(one)))
    x = np.tile(one, reps)[:n] * 10 ** (gain_db / 20)
    if voice is not None:
        v = np.abs(voice[:n])
        w = int(0.05 * SR)
        envv = np.convolve(v, np.ones(w) / w, mode="same")  # 목소리 크기
        on = np.clip(envv / 0.02, 0, 1)
        k = int(0.25 * SR)  # 줄이고 돌아오는 속도
        on = np.convolve(on, np.ones(k) / k, mode="same")
        x *= 1 - (1 - 10 ** (-duck_db / 20)) * on
    f = int(fade * SR)
    x[:int(0.3 * SR)] *= np.linspace(0, 1, int(0.3 * SR))
    x[-f:] *= np.linspace(1, 0, f)
    return x.astype(np.float32)
