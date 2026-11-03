"""효과음 — 전부 numpy 로 합성한다. 음원 파일·라이선스·구독이 필요 없다.

테마마다 '사건 → 소리' 표(BANKS)가 있다. 사건 종류:
  transition(장면 전환) cover(표지 등장) hit(큰 숫자) row(표·목록 한 줄) ok(체크) no(✕)
  step(단계) strike(취소선) type(코드 한 줄) shot(화면 캡처) end(끝 카드)
같은 소리가 기계처럼 반복되지 않게 사건마다 seed 를 바꿔 결·길이·음높이를 조금씩 흔든다.
"""
from __future__ import annotations

import numpy as np

SR = 48000


# ---------- 재료 ----------
def _t(sec):
    n = int(sec * SR)
    return n, np.arange(n) / SR


def env(n, attack=0.004, decay=0.08):
    t = np.arange(n) / SR
    return np.minimum(t / attack, 1) * np.exp(-t / decay)


def lp(x, k):
    """1극 저역통과(k 0~1, 클수록 밝다). k 는 상수나 배열."""
    out, acc = np.empty_like(x), 0.0
    kk = np.broadcast_to(np.asarray(k, dtype=float), x.shape)
    for i in range(len(x)):
        acc += kk[i] * (x[i] - acc)
        out[i] = acc
    return out


def bp(x, lo, hi):
    return lp(x, hi) - lp(x, lo)


def sine_sweep(f, t):
    return np.sin(2 * np.pi * np.cumsum(f) / SR) if np.ndim(f) else np.sin(2 * np.pi * f * t)


def square(f, t):
    return np.sign(sine_sweep(f, t))


# ---------- 지면(paper): 종이·연필·책상 ----------
def page(r):
    n, t = _t(r.uniform(0.30, 0.42))
    noise = bp(r.standard_normal(n), 0.05, r.uniform(0.35, 0.5))
    grains = np.zeros(n)
    for c in r.uniform(0.05, 0.85, 14) * n:
        w = r.uniform(0.004, 0.02) * SR
        grains += r.uniform(0.3, 1.0) * np.exp(-0.5 * ((np.arange(n) - c) / w) ** 2)
    body = np.sin(np.linspace(0, np.pi, n)) ** 1.5
    return noise * (0.35 * body + 0.65 * grains * body)


def pencil(r):
    n, t = _t(0.07)
    scratch = bp(r.standard_normal(n), 0.12, 0.7) * np.exp(-t / r.uniform(0.006, 0.012))
    return scratch * 1.6 + np.sin(2 * np.pi * r.uniform(170, 240) * t) * np.exp(-t / 0.012) * 0.5


def desk(r):
    n, t = _t(0.22)
    thud = lp(r.standard_normal(n), 0.015) * np.exp(-t / 0.035) * 9
    return thud + sine_sweep(r.uniform(70, 90) + 40 * np.exp(-t / 0.015), t) * np.exp(-t / 0.05) * 0.8


def pen_strike(r):
    n, t = _t(r.uniform(0.28, 0.36))
    fr = bp(r.standard_normal(n), 0.08, 0.45)
    flutter = 1 + 0.3 * lp(r.standard_normal(n), 0.002) * 8
    return fr * flutter * np.minimum(t / 0.02, 1) * np.minimum((t[-1] - t) / 0.06, 1)


def slide(r):
    n, _ = _t(0.45)
    return lp(r.standard_normal(n), 0.18) * np.sin(np.linspace(0, np.pi, n)) ** 1.5


# ---------- 네온(neon): 신스·글리치·디지털 ----------
def glitch(r):
    n, t = _t(0.26)
    out = np.zeros(n)
    for _ in range(7):  # 잘게 끊긴 디지털 조각
        i, m = int(r.uniform(0, 0.2) * SR), int(r.uniform(0.008, 0.03) * SR)
        f = r.uniform(300, 2400)
        out[i:i + m] += square(f, t[:m])[: len(out[i:i + m])] * r.uniform(0.2, 0.5)
    crush = np.round(r.standard_normal(n) * 3) / 3 * np.exp(-t / 0.08) * 0.4
    return out + crush


def sub_hit(r):
    n, t = _t(0.7)
    boom = sine_sweep(45 + 110 * np.exp(-t / 0.05), t) * env(n, 0.002, 0.25)
    return boom * 1.4 + bp(r.standard_normal(n), 0.1, 0.6) * env(n, 0.001, 0.02) * 0.4


def blip(r, k=0):
    n, t = _t(0.1)
    f = 880 * 2 ** (k * 2 / 12) * r.uniform(0.99, 1.01)
    return (np.sin(2 * np.pi * f * t) + 0.3 * square(f * 2, t)) * env(n, 0.002, 0.03)


def err_buzz(r):
    n, t = _t(0.36)
    return square(110, t) * 0.4 * ((t % 0.18) < 0.13) * np.exp(-t / 0.4)


def zap(r):
    n, t = _t(0.3)
    return square(2400 * np.exp(-t / 0.06) + 120, t) * 0.4 * env(n, 0.001, 0.12)


def key(r):
    n, t = _t(0.05)
    return bp(r.standard_normal(n), 0.2, 0.9) * env(n, 0.0005, 0.006) + np.sin(2 * np.pi * 1900 * t) * env(n, 0.0005, 0.01) * 0.3


def scan(r):
    n, t = _t(0.7)
    f = 300 + 900 * t / t[-1]
    return (np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.3 + r.standard_normal(n) * 0.08) * np.sin(np.linspace(0, np.pi, n))


def riser(r):
    n, t = _t(0.9)
    tone = sine_sweep(220 * 2 ** (t / t[-1] * 1.5), t) * 0.35
    return (tone + r.standard_normal(n) * 0.2 * np.linspace(0.2, 1, n)) * np.linspace(0, 1, n) ** 2


# ---------- 아케이드(arcade): 8비트 사각파 ----------
def jump(r):
    n, t = _t(0.18)
    return square(300 + 900 * t / t[-1], t) * 0.35 * env(n, 0.002, 0.12)


def powerup(r):
    n, t = _t(0.42)
    notes = np.array([523, 659, 784, 1047]) * r.uniform(0.98, 1.02)
    f = notes[np.minimum((t / 0.07).astype(int), 3)]
    return square(f, t) * 0.3 * np.exp(-np.maximum(t - 0.28, 0) / 0.08)


def coin(r):
    n, t = _t(0.3)
    return square(np.where(t < 0.06, 988, 1319), t) * 0.3 * np.exp(-np.maximum(t - 0.06, 0) / 0.1)


def bump(r):
    n, t = _t(0.3)
    return square(np.where(t < 0.12, 330, 220), t) * 0.35 * np.exp(-t / 0.25)


def explode(r):
    n, t = _t(0.45)
    hold = np.repeat(r.standard_normal(n // 40 + 1), 40)[:n]  # 거친 8비트 잡음
    return np.sign(hold) * 0.35 * np.exp(-t / 0.15)


def select(r):
    n, t = _t(0.08)
    return square(1568, t) * 0.25 * env(n, 0.001, 0.04)


def fanfare(r):
    n, t = _t(0.7)
    seq = [(0, 784), (0.1, 988), (0.2, 1175), (0.32, 1568)]
    f = np.full(n, 784.0)
    for s, fr in seq:
        f[t >= s] = fr
    return square(f, t) * 0.28 * np.exp(-np.maximum(t - 0.45, 0) / 0.1)


# ---------- 차분(calm): 바람·물방울·나무·종 ----------
def breeze(r):
    n, _ = _t(0.6)
    return lp(r.standard_normal(n), np.linspace(0.01, 0.05, n)) * np.sin(np.linspace(0, np.pi, n)) ** 2 * 4


def bell(r):
    n, t = _t(1.2)
    f0 = r.choice([784, 880, 988])
    out = sum(a * np.sin(2 * np.pi * f0 * m * t) * np.exp(-t / d) for m, a, d in ((1, 0.6, 0.5), (2.76, 0.2, 0.25), (5.4, 0.08, 0.12)))
    return out * np.minimum(t / 0.003, 1)


def drop(r):
    n, t = _t(0.18)
    f = r.uniform(900, 1300) * (1 + 1.2 * np.exp(-t / 0.02))
    return sine_sweep(f, t) * env(n, 0.001, 0.04)


def wood(r):
    n, t = _t(0.12)
    f = r.uniform(600, 820)
    return (np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * f * 2.3 * t)) * env(n, 0.001, 0.025)


def brush(r):
    n, t = _t(0.4)
    return bp(r.standard_normal(n), 0.03, 0.2) * np.sin(np.linspace(0, np.pi, n)) ** 0.8 * 1.4


def chime(r):
    n, t = _t(0.9)
    a = np.sin(2 * np.pi * 988 * t) * env(n, 0.002, 0.25)
    b = np.roll(np.sin(2 * np.pi * 1319 * t) * env(n, 0.002, 0.3), int(0.14 * SR))
    return (a + b) * 0.5


# ---------- 뉴스(news): 방송 스팅어·타자기·셔터 ----------
def swoosh(r):
    n, _ = _t(0.38)
    return lp(r.standard_normal(n), np.linspace(0.02, 0.35, n)) * np.sin(np.linspace(0, np.pi, n)) ** 2


def stinger(r):
    n, t = _t(0.9)
    chord = sum(np.sign(np.sin(2 * np.pi * f * t)) * 0.12 + np.sin(2 * np.pi * f * t) * 0.2 for f in (110, 164.8, 220, 277.2))
    boom = sub_hit(r)
    return lp(chord, 0.15) * env(n, 0.004, 0.35) * 2 + np.pad(boom, (0, max(0, n - len(boom))))[:n] * 0.6


def tick(r):
    n, t = _t(0.06)
    return (np.sin(2 * np.pi * 1850 * t) * 0.6 + np.sin(2 * np.pi * 2900 * t) * 0.25) * env(n, 0.002, 0.012)


def stamp(r):
    n, t = _t(0.32)
    thud = sine_sweep(90 + 60 * np.exp(-t / 0.02), t) * env(n, 0.001, 0.09)
    return thud * 1.5 + r.standard_normal(n) * env(n, 0.001, 0.025) * 0.5


def typewriter(r):
    n, t = _t(0.28)
    out = np.zeros(n)
    for k in range(4):
        i = int((k * 0.06 + r.uniform(0, 0.015)) * SR)
        m = int(0.02 * SR)
        out[i:i + m] += bp(r.standard_normal(m), 0.15, 0.8) * env(m, 0.0005, 0.004)
    return out * 1.6


def shutter(r):
    n, t = _t(0.16)
    a = bp(r.standard_normal(n), 0.1, 0.7) * env(n, 0.0005, 0.01)
    return a + np.roll(a, int(0.07 * SR)) * 0.7


GEN = {f.__name__: f for f in (page, pencil, desk, pen_strike, slide, glitch, sub_hit, blip, err_buzz, zap, key, scan,
                              riser, jump, powerup, coin, bump, explode, select, fanfare, breeze, bell, drop, wood,
                              brush, chime, swoosh, stinger, tick, stamp, typewriter, shutter)}

BANKS = {
    "paper": dict(transition="page", cover="desk", hit="desk", row="pencil", ok="pencil", no="pen_strike",
                  step="pencil", strike="pen_strike", type="pencil", shot="slide", end="desk"),
    "neon": dict(transition="glitch", cover="riser", hit="sub_hit", row="blip", ok="blip", no="err_buzz",
                 step="blip", strike="zap", type="key", shot="scan", end="sub_hit"),
    "arcade": dict(transition="jump", cover="powerup", hit="coin", row="coin", ok="coin", no="bump",
                   step="select", strike="explode", type="select", shot="jump", end="fanfare"),
    "calm": dict(transition="breeze", cover="bell", hit="bell", row="drop", ok="wood", no="wood",
                 step="drop", strike="brush", type="wood", shot="breeze", end="chime"),
    "news": dict(transition="swoosh", cover="stinger", hit="stamp", row="tick", ok="tick", no="err_buzz",
                 step="tick", strike="stamp", type="typewriter", shot="shutter", end="stinger"),
}
LEVEL = {"transition": 0.10, "cover": 0.16, "hit": 0.2, "end": 0.16, "strike": 0.15}  # 사건별 목표 RMS(그 밖 0.12)


def make(name: str, seed: int = 0, step: int = 0, rms: float = 0.12) -> np.ndarray:
    r = np.random.default_rng(1000 + seed * 7 + len(name))
    x = GEN[name](r, step) if name == "blip" else GEN[name](r)
    x = np.asarray(x, dtype=np.float64)
    return (x * (rms / max(1e-6, float(np.sqrt((x ** 2).mean()))))).astype(np.float32)


def for_event(theme: str, event: str, seed: int, step: int = 0) -> np.ndarray:
    """테마의 사건 소리. spec 의 "sfx": {"row": "coin"} 처럼 편마다 바꿀 수 있게 이름도 그대로 받는다."""
    name = BANKS[theme].get(event, event)
    return make(name, seed, step, LEVEL.get(event, 0.12))
