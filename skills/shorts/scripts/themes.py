"""테마 = 색 + 배경 + 장면 전환 + 화면 테두리(채널 이름·진행선·자막) + 표지 그림 + 효과음 묶음(sfx.BANKS).

  paper  지면     밝은 종이, 빨강 강조, 겹치는 페이드, 종이·연필 소리      → 정보·정리·코딩 팁·리뷰
  neon   네온     어두운 화면, 하늘·분홍 빛, 글리치 전환, 신스·디지털 소리 → AI·보안·해킹·미래 기술
  arcade 아케이드 남보라 밤하늘, 노랑, 픽셀 전환, 8비트 소리           → 게임·재미·입문·퀴즈
  calm   차분     따뜻한 크림, 초록·흙빛, 느린 페이드, 바람·물방울·종      → 건강·요리·여행·자기계발
  news   뉴스     흰 지면 + 남색 띠, 빨강, 밀어내기 전환, 방송 스팅어      → 속보·경제·정책·발표

themes.use("neon") 를 레이어를 만들기 전에 한 번 부른다. 레이어는 P(현재 팔레트)를 읽는다.
"""
from __future__ import annotations

import math
from pathlib import Path
from functools import lru_cache

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from engine import H, W, ease_in_out, paste, prog, rrect, text_img

M = 72
TOP_SAFE = 64  # 쇼츠 플레이어가 위를 조금 가린다 → 지면 전체를 이만큼 내린다(아래 끝은 원래 비워 둔 자리)

PALETTES = {
    "paper": dict(bg=(250, 250, 248), ink=(20, 20, 20), body=(65, 65, 63), mute=(113, 113, 108), rule=(215, 215, 210),
                  accent=(214, 44, 22), accent2=(20, 20, 20), panel=(240, 240, 237), ok=(34, 139, 84), on_accent=(250, 250, 248)),
    "neon": dict(bg=(9, 12, 24), ink=(236, 242, 255), body=(178, 190, 215), mute=(120, 132, 160), rule=(46, 56, 86),
                 accent=(62, 232, 255), accent2=(255, 62, 160), panel=(18, 24, 44), ok=(80, 255, 170), on_accent=(9, 12, 24),
                 glow=(62, 232, 255)),
    "arcade": dict(bg=(24, 20, 58), ink=(255, 255, 255), body=(208, 204, 240), mute=(150, 144, 200), rule=(70, 62, 130),
                   accent=(255, 212, 63), accent2=(255, 92, 160), panel=(36, 30, 84), ok=(110, 240, 120), on_accent=(24, 20, 58),
                   outline=(12, 8, 30)),
    "calm": dict(bg=(247, 242, 232), ink=(46, 52, 40), body=(84, 88, 72), mute=(132, 128, 110), rule=(222, 212, 192),
                 accent=(196, 98, 58), accent2=(98, 128, 88), panel=(239, 231, 216), ok=(98, 128, 88), on_accent=(247, 242, 232)),
    "news": dict(bg=(244, 245, 248), ink=(14, 26, 52), body=(56, 66, 90), mute=(110, 118, 138), rule=(212, 216, 226),
                 accent=(222, 34, 44), accent2=(16, 42, 92), panel=(232, 235, 242), ok=(22, 130, 80), on_accent=(255, 255, 255)),
}
P: dict = dict(PALETTES["paper"])
NAME = "paper"
BRAND = "MY CHANNEL"
LABEL = ""
FOOTER = "AI 음성"


SFX_BANK = "paper"


def _rgb(v):
    if isinstance(v, str):
        v = v.lstrip("#")
        return tuple(int(v[i:i + 2], 16) for i in (0, 2, 4))
    return tuple(v)


def use(theme, brand: str = "MY CHANNEL", label: str = "", footer: str = "AI 음성"):
    """theme = 기본 테마 이름, 또는 사용자 테마 {"base": "neon", "colors": {"accent": "#ff8800", "bg": "#101010"},
    "fonts": {"heavy": "fonts/MyFont.ttf"}, "sfx": "arcade"} — 색·글꼴·효과음 묶음을 기본 테마 위에 덮어쓴다."""
    global NAME, BRAND, LABEL, FOOTER, SFX_BANK
    import engine
    spec = {"base": theme} if isinstance(theme, str) else dict(theme)
    name = spec.get("base", "paper")
    if name not in PALETTES:
        raise SystemExit(f"모르는 테마 {name!r} — {', '.join(PALETTES)} 중 하나 (사용자 테마는 base 로 고른다)")
    NAME, BRAND, LABEL, FOOTER, SFX_BANK = name, brand, label, footer, spec.get("sfx", name)
    P.clear()
    P.update(PALETTES[name])
    P.update({k: _rgb(v) for k, v in (spec.get("colors") or {}).items()})
    if name == "neon" and "glow" not in (spec.get("colors") or {}):
        P["glow"] = P["accent"]  # 네온 빛은 강조색을 따라간다
    for weight, path in (spec.get("fonts") or {}).items():
        engine.FONT_FILES[weight] = Path(path).expanduser()
    engine.font.cache_clear()
    text_img.cache_clear()
    background.cache_clear()
    hero.cache_clear()
    return Theme()


def T(txt, weight="heavy", size=48, color=None, max_w=W - 2 * M, align="left", lh=1.2, accent=None):
    """테마 글자: 강조어 [ ] 는 accent, 네온은 강조어에 빛, 아케이드는 굵은 테두리."""
    return text_img(txt, weight, size, color or P["ink"], accent or P["accent"], max_w, align, lh,
                    P.get("glow") if size >= 40 else None, P.get("outline") if size >= 40 else None)


# ---------- 배경 ----------
@lru_cache(maxsize=1)
def background(_t=0.0):
    img = Image.new("RGBA", (W, H), P["bg"] + (255,))
    d = ImageDraw.Draw(img)
    if NAME == "neon":  # 옅은 격자 + 위쪽 푸른 빛
        for x in range(0, W, 90):
            d.line([(x, 0), (x, H)], fill=(255, 255, 255, 10))
        for y in range(0, H, 90):
            d.line([(0, y), (W, y)], fill=(255, 255, 255, 10))
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(glow).ellipse([-200, -600, 1280, 500], fill=P["accent"] + (26,))
        img.alpha_composite(glow.filter(ImageFilter.GaussianBlur(180)))
    elif NAME == "arcade":  # 픽셀 별
        rng = np.random.default_rng(3)
        for _ in range(90):
            x, y, s = int(rng.uniform(0, W)), int(rng.uniform(0, H)), int(rng.choice([4, 6, 8]))
            d.rectangle([x, y, x + s, y + s], fill=(255, 255, 255, int(rng.uniform(30, 90))))
    elif NAME == "calm":  # 위에서 아래로 따뜻하게 짙어지고, 귀퉁이에 옅은 해
        grad = np.linspace(0, 1, H)[:, None, None] * np.array([-8, -12, -18])[None, None, :]
        arr = np.clip(np.array(img.convert("RGB"), dtype=float) + grad, 0, 255).astype(np.uint8)
        img = Image.fromarray(arr).convert("RGBA")
        sun = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(sun).ellipse([640, -260, 1340, 440], fill=P["accent"] + (22,))
        img.alpha_composite(sun.filter(ImageFilter.GaussianBlur(60)))
    elif NAME == "news":  # 위쪽 남색 띠
        d.rectangle([0, 0, W, 186], fill=P["accent2"] + (255,))
    return img


# ---------- 표지 그림(사진이 없을 때) ----------
@lru_cache(maxsize=4)
def hero(w: int, h: int, name: str = "") -> Image.Image:
    name = name or NAME
    im = Image.new("RGBA", (w, h), P["panel"] + (255,))
    d = ImageDraw.Draw(im)
    if name == "paper":
        for x in range(-h, w, 26):
            d.line([(x, h), (x + h, 0)], fill=P["rule"] + (255,), width=3)
        d.rectangle([0, h - 28, int(w * 0.38), h], fill=P["accent"] + (255,))
    elif name == "neon":  # 신스웨이브: 해 + 원근 격자
        d.rectangle([0, 0, w, h], fill=(14, 10, 40, 255))
        sun = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sun)
        r = int(h * 0.42)
        for k in range(r, 0, -2):
            c = tuple(int(a + (b - a) * k / r) for a, b in zip(P["accent"], P["accent2"]))
            sd.ellipse([w / 2 - k, h * 0.58 - k, w / 2 + k, h * 0.58 + k], fill=c + (255,))
        for y in range(int(h * 0.30), int(h * 0.58), 18):
            sd.rectangle([0, y, w, y + (y - h * 0.30) / 30 + 2], fill=(0, 0, 0, 0))
        im.alpha_composite(sun.filter(ImageFilter.GaussianBlur(1)))
        hz = int(h * 0.58)
        d.rectangle([0, hz, w, h], fill=(10, 8, 30, 255))
        for k in range(1, 12):
            y = hz + (h - hz) * (k / 11) ** 2
            d.line([(0, y), (w, y)], fill=P["accent2"] + (200,), width=2)
        for k in range(-12, 13):
            d.line([(w / 2 + k * 30, hz), (w / 2 + k * 180, h)], fill=P["accent2"] + (200,), width=2)
        d.line([(0, hz), (w, hz)], fill=P["accent"] + (255,), width=4)
    elif name == "arcade":  # 픽셀 산 + 네모 해
        px = 16
        d.rectangle([w * 0.68, h * 0.14, w * 0.68 + px * 7, h * 0.14 + px * 7], fill=P["accent"] + (255,))
        rng = np.random.default_rng(5)
        for layer, col in ((0.55, P["rule"]), (0.72, P["accent2"])):
            y = h * layer
            for x in range(0, w, px):
                y = min(h - px, max(h * (layer - 0.2), y + rng.choice([-px, 0, px])))
                d.rectangle([x, y, x + px, h], fill=col + (255,))
        for _ in range(30):
            x, y = int(rng.uniform(0, w)) // px * px, int(rng.uniform(0, h * 0.4)) // px * px
            d.rectangle([x, y, x + 6, y + 6], fill=(255, 255, 255, 160))
    elif name == "calm":  # 겹친 언덕 + 해
        d.ellipse([w * 0.62, h * 0.12, w * 0.62 + h * 0.4, h * 0.52], fill=P["accent"] + (150,))
        for k, col in enumerate(((198, 210, 176), (150, 176, 132), P["accent2"])):
            pts = [(x, h * (0.55 + 0.12 * k) + math.sin(x / w * math.pi * (1.4 + k * 0.5) + k) * h * 0.08)
                   for x in range(0, w + 20, 20)]
            d.polygon(pts + [(w, h), (0, h)], fill=col + (255,))
    elif name == "news":  # 남색 판 + 지구본 선 + 빨강 띠
        d.rectangle([0, 0, w, h], fill=P["accent2"] + (255,))
        cx, cy, r = w * 0.72, h * 0.5, h * 0.62
        for k in range(1, 6):
            d.ellipse([cx - r * k / 5, cy - r, cx + r * k / 5, cy + r], outline=(255, 255, 255, 70), width=3)
        for k in range(-4, 5):
            y = cy + r * k / 5
            hw = r * math.sqrt(max(0.0, 1 - (k / 5) ** 2))
            d.line([(cx - hw, y), (cx + hw, y)], fill=(255, 255, 255, 70), width=3)
        d.rectangle([0, h - 34, w, h], fill=P["accent"] + (255,))
    return im


class Theme:
    @property
    def xfade(self):
        return {"calm": 0.5, "news": 0.32, "arcade": 0.36, "neon": 0.3}.get(NAME, 0.28)

    def background(self, t):
        return background()

    # ---------- 장면 전환 ----------
    def transition(self, cv, prev, cur, p):
        if NAME == "neon":
            src = prev if p < 0.5 else cur
            k = 1 - abs(p - 0.5) * 2  # 가운데서 가장 세게
            cv.alpha_composite(_glitch(src, k, int(p * 12)))
        elif NAME == "arcade":
            src = prev if p < 0.5 else cur
            k = 1 - abs(p - 0.5) * 2
            b = max(1, int(2 + 46 * k))
            small = src.resize((max(1, W // b), max(1, H // b)), Image.NEAREST)
            cv.alpha_composite(small.resize((W, H), Image.NEAREST))
        elif NAME == "news":
            e = ease_in_out(p)
            cv.alpha_composite(prev, (int(-W * e), 0))
            cv.alpha_composite(cur, (int(W * (1 - e)), 0))
        else:  # paper·calm: 겹치는 페이드 (calm 은 더 길고 부드럽게)
            e = ease_in_out(p) if NAME == "calm" else p
            prev = prev.copy()
            prev.putalpha(prev.getchannel("A").point(lambda a: int(a * (1 - e))))
            cur = cur.copy()
            cur.putalpha(cur.getchannel("A").point(lambda a: int(a * e)))
            cv.alpha_composite(prev)
            cv.alpha_composite(cur)

    # ---------- 테두리: 채널 이름 · 진행선 · 자막 · 아래 문구 ----------
    def overlay(self, cv, t, total, caps):
        d = ImageDraw.Draw(cv)
        frac = min(1.0, t / total)
        brand_col = {"neon": P["accent"], "arcade": P["accent"], "news": (255, 255, 255)}.get(NAME, P["ink"])
        paste(cv, T(BRAND, "heavy", 40, brand_col, 640), (M, 84))
        if LABEL:
            if NAME == "news":
                pill = T(LABEL, "heavy", 26, P["on_accent"], 420)
                paste(cv, rrect(pill.width + 28, 46, 4, fill=P["accent"] + (255,)), (W - M, 90), anchor="rt")
                paste(cv, pill, (W - M - 14, 113), anchor="rm")
            else:
                paste(cv, T(LABEL, "medium", 28, P["mute"], 420, "right"), (W - M, 96), anchor="rt")
        if NAME == "paper":
            d.line([(M, 150), (W - M, 150)], fill=P["ink"], width=3)
            d.line([(M, 158), (W - M, 158)], fill=P["ink"], width=1)
            d.line([(M, 150), (M + int((W - 2 * M) * frac), 150)], fill=P["accent"], width=3)
        elif NAME == "neon":
            d.line([(M, 156), (W - M, 156)], fill=P["rule"], width=2)
            bar = Image.new("RGBA", (W, 40), (0, 0, 0, 0))
            ImageDraw.Draw(bar).line([(M, 20), (M + int((W - 2 * M) * frac), 20)], fill=P["accent"] + (255,), width=4)
            cv.alpha_composite(bar.filter(ImageFilter.GaussianBlur(5)), (0, 136))
            cv.alpha_composite(bar, (0, 136))
        elif NAME == "arcade":
            n = 18
            bw = (W - 2 * M - (n - 1) * 6) / n
            for k in range(n):
                on = k < round(frac * n)
                x = M + k * (bw + 6)
                d.rectangle([x, 150, x + bw, 166], fill=(P["accent"] if on else P["rule"]) + (255,))
        elif NAME == "calm":
            paste(cv, rrect(W - 2 * M, 6, 3, fill=P["rule"] + (255,)), (M, 152))
            if frac > 0.01:
                paste(cv, rrect(max(6, int((W - 2 * M) * frac)), 6, 3, fill=P["accent2"] + (255,)), (M, 152))
        elif NAME == "news":
            d.rectangle([0, 186, int(W * frac), 194], fill=P["accent"] + (255,))

        for c in caps:
            if c.t0 <= t < c.t1:
                self._caption(cv, c.text, prog(t, c.t0, 0.14))
                break
        if FOOTER:
            paste(cv, T(FOOTER, "medium", 24, P["mute"], W - 2 * M, "center"), (W / 2, 1650), anchor="mt", alpha=0.9)
        if TOP_SAFE:
            body = cv.crop((0, 0, W, cv.height - TOP_SAFE))
            cv.paste(P["bg"] + (255,), (0, 0, W, cv.height))
            cv.paste(body, (0, TOP_SAFE))
            if NAME == "news":  # 내려간 만큼 위쪽 띠를 이어 칠한다
                ImageDraw.Draw(cv).rectangle([0, 0, W, TOP_SAFE], fill=P["accent2"] + (255,))

    def _caption(self, cv, text, p):
        y = 1430 + (1 - p) * 8
        if NAME == "news":
            img = text_img(text, "heavy", 54, (255, 255, 255), (255, 214, 90), W - 2 * M - 40, "center", 1.25)
            paste(cv, rrect(W - 2 * M, img.height + 30, 8, fill=P["accent2"] + (235,)), (W / 2, y), alpha=p, anchor="mm")
            paste(cv, img, (W / 2, y + 4), alpha=p, anchor="mm")
        elif NAME == "neon":
            img = text_img(text, "heavy", 56, (255, 255, 255), P["accent"], W - 2 * M - 40, "center", 1.25, P["accent"])
            paste(cv, rrect(W - 2 * M, img.height + 20, 18, fill=(4, 6, 14, 190)), (W / 2, y), alpha=p, anchor="mm")
            paste(cv, img, (W / 2, y), alpha=p, anchor="mm")
        elif NAME == "arcade":
            img = text_img(text, "heavy", 58, (255, 255, 255), P["accent"], W - 2 * M, "center", 1.25, None, (12, 8, 30))
            paste(cv, img, (W / 2, y), alpha=p, anchor="mm")
        else:
            img = text_img(text, "heavy", 56, P["ink"], P["accent"], W - 2 * M, "center", 1.25)
            paste(cv, img, (W / 2, y), alpha=p, anchor="mm")


def _glitch(src, k, seed):
    """가로 띠를 엇갈리게 밀고 빨강·파랑 채널을 벌린다. k 0~1."""
    if k < 0.05:
        return src
    rng = np.random.default_rng(seed)
    arr = np.array(src)
    out = arr.copy()
    y = 0
    while y < H:
        h = int(rng.uniform(30, 160))
        dx = int(rng.uniform(-1, 1) * 90 * k)
        out[y:y + h] = np.roll(arr[y:y + h], dx, axis=1)
        y += h
    s = int(14 * k)
    if s:
        out[..., 0] = np.roll(out[..., 0], s, axis=1)
        out[..., 2] = np.roll(out[..., 2], -s, axis=1)
    return Image.fromarray(out, "RGBA")
