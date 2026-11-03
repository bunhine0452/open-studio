"""세로 쇼츠(1080×1920) 렌더링 기본기: 글자·도형·보간·장면·FFmpeg 인코딩.

테마(themes.py)가 배경·장면 전환·화면 테두리(마스트헤드·자막)를 정하고, 장면 레이어(layers.py)가 그 위에 그린다.
"""
from __future__ import annotations

import math
import re
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

W, H, FPS = 1080, 1920, 30
FONTS = Path(__file__).resolve().parents[1] / "fonts"
FONT_FILES = {
    "heavy": FONTS / "Pretendard-Black.otf",
    "extrabold": FONTS / "Pretendard-ExtraBold.otf",
    "bold": FONTS / "Pretendard-Bold.otf",
    "medium": FONTS / "Pretendard-Medium.otf",
}
MONO_CANDIDATES = ("/System/Library/Fonts/Menlo.ttc", "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
                   "C:/Windows/Fonts/consola.ttf")
SS = 3  # 도형 안티앨리어싱 슈퍼샘플 배율


# ---------- 시간·보간 ----------
def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def ease_out(t):
    return 1 - (1 - clamp(t)) ** 3


def ease_in_out(t):
    t = clamp(t)
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def prog(t, t0, dur, ease=ease_out):
    return ease((t - t0) / dur) if dur > 0 else float(t >= t0)


def lerp(a, b, p):
    return a + (b - a) * p


# ---------- 글자 ----------
@lru_cache(maxsize=None)
def font(weight: str, size: int):
    if weight == "mono":
        for p in MONO_CANDIDATES:
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
        return ImageFont.load_default()
    return ImageFont.truetype(str(FONT_FILES.get(weight, FONT_FILES["bold"])), size)


def parse_rich(text: str):
    """'[강조]' 표기를 (글자, 강조 여부) 조각으로 나눈다."""
    return [(m.group(1) or m.group(2), m.group(1) is not None) for m in re.finditer(r"\[([^\]]+)\]|([^\[]+)", text)]


def wrap_runs(runs, fnt, max_w):
    lines, cur, cur_w, tokens = [], [], 0, []
    for txt, acc in runs:
        for part in txt.split("\n"):
            tokens.extend((w, acc) for w in re.findall(r"\s+|\S+\s*", part))
            tokens.append(("\n", acc))
        tokens.pop()
    for tok, acc in tokens:
        if tok == "\n":
            lines.append(cur)
            cur, cur_w = [], 0
            continue
        if not cur and not tok.strip():
            continue
        if cur and cur_w + fnt.getlength(tok.rstrip()) > max_w:
            lines.append(cur)
            cur, cur_w = [], 0
        cur.append((tok, acc))
        cur_w += fnt.getlength(tok)
    lines.append(cur)
    return lines


@lru_cache(maxsize=1024)
def text_img(text, weight="bold", size=48, color=(20, 20, 20), accent=(214, 44, 22), max_w=936, align="left",
             line_h=1.25, glow=None, outline=None):
    """여러 줄 글자 이미지. glow=(r,g,b) 면 강조 글자 둘레에 빛, outline=(r,g,b) 면 전체에 굵은 테두리."""
    fnt = font(weight, size)
    lines = wrap_runs(parse_rich(text), fnt, max_w)
    lh = int(size * line_h)
    widths = [sum(fnt.getlength(t) for t, _ in ln) for ln in lines]
    pad = int(size * 0.25) if (glow or outline) else 0
    w = int(max(widths + [1])) + 8 + pad * 2
    h = lh * len(lines) + int(size * 0.3) + pad * 2
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    stroke = max(2, size // 14) if outline else 0
    for i, ln in enumerate(lines):
        x = pad + {"left": 0, "center": (w - 2 * pad - widths[i]) / 2, "right": w - 2 * pad - widths[i]}[align]
        for tok, acc in ln:
            d.text((x, pad + i * lh), tok, font=fnt, fill=(accent if acc else color) + (255,),
                   stroke_width=stroke, stroke_fill=(outline + (255,)) if outline else None)
            x += fnt.getlength(tok)
    if glow:
        halo = Image.new("RGBA", img.size, glow + (0,))
        halo.putalpha(img.getchannel("A").filter(ImageFilter.GaussianBlur(size / 7)).point(lambda a: int(a * 0.85)))
        halo.alpha_composite(img)
        img = halo
    return img


def paste(canvas, img, xy, alpha=1.0, anchor="lt"):
    if alpha <= 0.001:
        return
    x, y = xy
    if anchor[0] == "m":
        x -= img.width / 2
    if anchor[0] == "r":
        x -= img.width
    if anchor[1] == "m":
        y -= img.height / 2
    if anchor[1] == "b":
        y -= img.height
    if alpha < 0.999:
        img = img.copy()
        img.putalpha(img.getchannel("A").point(lambda a: int(a * alpha)))
    canvas.alpha_composite(img, (int(round(x)), int(round(y))))


@lru_cache(maxsize=1024)
def rrect(w, h, r, fill=None, outline=None, width=0):
    w, h = max(int(w), 2), max(int(h), 2)
    big = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(big)
    box = [0, 0, w * SS - 1, h * SS - 1]
    if fill is not None:
        d.rounded_rectangle(box, r * SS, fill=fill)
    if outline is not None and width:
        d.rounded_rectangle(box, r * SS, outline=outline, width=width * SS)
    return big.resize((w, h), Image.LANCZOS)


@lru_cache(maxsize=64)
def check_icon(size=44, color=(34, 139, 84)):
    s = size * SS
    big = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    ImageDraw.Draw(big).line([(s * .15, s * .52), (s * .40, s * .76), (s * .86, s * .24)], fill=color + (255,),
                             width=int(s * .13), joint="curve")
    return big.resize((size, size), Image.LANCZOS)


@lru_cache(maxsize=64)
def x_icon(size=44, color=(214, 44, 22)):
    s = size * SS
    im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.line([(s * .2, s * .2), (s * .8, s * .8)], fill=color + (255,), width=int(s * .13))
    d.line([(s * .8, s * .2), (s * .2, s * .8)], fill=color + (255,), width=int(s * .13))
    return im.resize((size, size), Image.LANCZOS)


# ---------- 장면 ----------
class Layer:
    t0: float = 0.0

    def draw(self, cv, t):  # t = 장면 안의 시각
        raise NotImplementedError


@dataclass
class Scene:
    t0: float
    t1: float
    layers: list


@dataclass
class Caption:
    t0: float
    t1: float
    text: str


def scene_frame(sc, t):
    cv = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for ly in sc.layers:
        ly.draw(cv, t - sc.t0)
    return cv


def frame_at(t, scenes, caps, total, theme):
    """배경 → (전환 중이면 테마의 전환 효과로 앞뒤 장면 섞기) → 테마 테두리·자막."""
    cv = theme.background(t).copy()
    cur = next((s for s in scenes if s.t0 <= t < s.t1), scenes[-1])
    idx = scenes.index(cur)
    layer = scene_frame(cur, t)
    dur = theme.xfade
    if idx > 0 and t - cur.t0 < dur:
        theme.transition(cv, scene_frame(scenes[idx - 1], t), layer, (t - cur.t0) / dur)
    else:
        cv.alpha_composite(layer)
    theme.overlay(cv, t, total, caps)
    return cv


def render(scenes, caps, total, out_path, audio_path, theme):
    n_frames = int(math.ceil(total * FPS))
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS),
           "-i", "-", "-i", str(audio_path), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium",
           "-crf", "19", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest",
           "-movflags", "+faststart", str(out_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    for f in range(n_frames):
        proc.stdin.write(frame_at(f / FPS, scenes, caps, total, theme).convert("RGB").tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg 실패")
