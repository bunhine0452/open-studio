"""장면 레이어. 색은 themes.P(현재 테마)에서 읽는다 — themes.use() 를 먼저 부를 것. 시각은 장면 안의 시각."""
from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter, ImageOps

import themes
from engine import W, Layer, check_icon, ease_in_out, ease_out, font, paste, prog, rrect, x_icon
from themes import M, P, T


class Fade(Layer):
    """살짝 올라오며 나타난다."""

    def __init__(self, img, xy, t0=0.0, anchor="lt", rise=14, dur=0.32):
        self.img, self.xy, self.t0, self.anchor, self.rise, self.dur = img, xy, t0, anchor, rise, dur

    def draw(self, cv, t):
        if t < self.t0:
            return
        p = prog(t, self.t0, self.dur)
        paste(cv, self.img, (self.xy[0], self.xy[1] + (1 - p) * self.rise), alpha=p, anchor=self.anchor)


class Head(Fade):
    """헤드라인(강조어 [ ]). 글자 수로 크기를 고른다."""

    def __init__(self, txt, t0, y=262, size=None):
        lines = txt.count("\n") + 1
        longest = max(len(x) for x in txt.replace("[", "").replace("]", "").split("\n"))
        size = size or (96 if longest <= 9 and lines <= 2 else 80 if longest <= 13 else 70)
        super().__init__(T(txt, "heavy", size, lh=1.14), (M, y), t0, rise=22, dur=0.45)


class Picture(Layer):
    """표지 그림 띠: 사진 경로가 있으면 사진, 없으면 테마 그림. 옆으로 펼쳐지고 천천히 당겨진다."""

    def __init__(self, path, box, t0=0.0, wipe=0.5):
        self.box, self.t0, self.wipe = box, t0, wipe
        x, y, w, h = box
        src = Image.open(path).convert("RGB") if path else themes.hero(w, h, themes.NAME).convert("RGB")
        self.src = ImageOps.fit(src, (int(w * 1.08), int(h * 1.08)), Image.LANCZOS)

    def draw(self, cv, t):
        if t < self.t0:
            return
        x, y, w, h = self.box
        z = 1.08 - 0.06 * min(1.0, (t - self.t0) / 6)
        sw, sh = int(w * z), int(h * z)
        ox, oy = (self.src.width - sw) // 2, (self.src.height - sh) // 2
        im = self.src.crop((ox, oy, ox + sw, oy + sh)).resize((w, h), Image.BILINEAR)
        p = ease_in_out(min(1.0, (t - self.t0) / self.wipe)) if self.wipe else 1
        cv.paste(im.crop((0, 0, max(1, int(w * p)), h)), (x, y))


class Tag(Layer):
    """강조색 꼬리표."""

    def __init__(self, text, xy, t0=0.0, size=32):
        self.text, self.xy, self.t0, self.size = text, xy, t0, size

    def draw(self, cv, t):
        if t < self.t0:
            return
        txt = T(self.text, "heavy", self.size, P["on_accent"])
        w, h = txt.width + 36, int(self.size * 1.75)
        p = ease_out(min(1.0, (t - self.t0) / 0.25))
        paste(cv, rrect(max(2, int(w * p)), h, 4 if themes.NAME != "calm" else h // 2, fill=P["accent"] + (255,)), self.xy)
        if p > 0.6:
            paste(cv, txt, (self.xy[0] + 18, self.xy[1] + h / 2 + 2), alpha=(p - 0.6) / 0.4, anchor="lm")


class CountUp(Layer):
    """큰 숫자가 0 에서 목표까지 올라가고, pulse_at 에 한 번 툭 커진다."""

    def __init__(self, target, xy, t0=0.0, dur=0.7, size=300, prefix="", suffix="", pulse_at=None, comma=None):
        self.comma = target >= 10000 if comma is None else comma  # 1984년에 쉼표가 붙지 않게
        self.target, self.xy, self.t0, self.dur, self.size = target, xy, t0, dur, size
        self.prefix, self.suffix, self.pulse_at = prefix, suffix, pulse_at

    def draw(self, cv, t):
        if t < self.t0:
            return
        n = round(self.target * ease_out(min(1.0, (t - self.t0) / self.dur)))
        img = T(f"{self.prefix}{n:,}{self.suffix}" if self.comma else f"{self.prefix}{n}{self.suffix}", "heavy", self.size, P["accent"], 1000)
        if self.pulse_at is not None and 0 <= t - self.pulse_at < 0.3:
            s = 1 + 0.06 * (1 - abs((t - self.pulse_at) / 0.15 - 1))
            img = img.resize((int(img.width * s), int(img.height * s)), Image.BILINEAR)
        paste(cv, img, self.xy, alpha=min(1.0, (t - self.t0) / 0.15))


class Rows(Layer):
    """괘선 표. rows=[(t, 왼쪽, 오른쪽|None, 'ok'|'no'|None, 강조?)]."""

    def __init__(self, rows, y, row_h=104, size=48):
        self.rows, self.y, self.row_h, self.size = rows, y, row_h, size
        self.t0 = min(r[0] for r in rows) - 0.01

    def draw(self, cv, t):
        d = ImageDraw.Draw(cv)
        last_y, width = None, W - 2 * M
        for k, (tr, left, right, mark, hot) in enumerate(self.rows):
            if t < tr:
                break
            y = self.y + k * self.row_h
            d.line([(M, y), (M + int(width * ease_out(min(1.0, (t - tr) / 0.3))), y)], fill=P["rule"], width=2)
            a = prog(t, tr + 0.08, 0.28)
            col = P["accent"] if hot else P["ink"]
            x = M
            if mark:
                icon = check_icon(46, P["ok"]) if mark == "ok" else x_icon(46, P["accent"])
                paste(cv, icon, (M, y + (self.row_h - 46) / 2), alpha=a)
                x = M + 76
            paste(cv, T(left, "bold", self.size, col, 640), (x, y + self.row_h / 2 + 2), alpha=a, anchor="lm")
            if right:
                paste(cv, T(right, "heavy", self.size, col, 400, "right"), (M + width, y + self.row_h / 2 + 2), alpha=a, anchor="rm")
            last_y = y + self.row_h
        if last_y is not None:
            d.line([(M, last_y), (M + width, last_y)], fill=P["rule"], width=2)


class Steps(Layer):
    """번호 단계. 마지막 단계는 강조색."""

    def __init__(self, items, y, gap=124, size=58):
        self.items, self.y, self.gap, self.size = items, y, gap, size
        self.t0 = items[0][0] - 0.01

    def draw(self, cv, t):
        d = ImageDraw.Draw(cv)
        for i, (ts, label) in enumerate(self.items):
            if t < ts:
                break
            last = i == len(self.items) - 1
            a = prog(t, ts, 0.25)
            y = self.y + i * self.gap
            col = P["accent"] if last else P["ink"]
            r = int(28 * (0.6 + 0.4 * a))
            if themes.NAME == "arcade":
                d.rectangle([M + 28 - r, y + 34 - r, M + 28 + r, y + 34 + r], fill=col + (255,))
            else:
                d.ellipse([M + 28 - r, y + 34 - r, M + 28 + r, y + 34 + r], fill=col + (255,))
            num_col = P["on_accent"] if last else P["bg"]
            paste(cv, T(str(i + 1), "heavy", 34, num_col, 60), (M + 28, y + 35), alpha=a, anchor="mm")
            paste(cv, T(label, "heavy" if last else "bold", self.size, col, 800), (M + 84 + (1 - a) * 12, y + 6), alpha=a)


class Strike(Layer):
    """큰 글자 위로 강조색 취소선."""

    def __init__(self, text, xy, t0=0.0, t_strike=1.0, size=220):
        self.img = T(text, "heavy", size, P["ink"], 1000)
        self.xy, self.t0, self.ts = xy, t0, t_strike

    def draw(self, cv, t):
        if t < self.t0:
            return
        x, y = self.xy
        paste(cv, self.img, (x, y), alpha=prog(t, self.t0, 0.25) * (1 - 0.55 * prog(t, self.ts + 0.25, 0.3)))
        if t >= self.ts:
            p = ease_out(min(1.0, (t - self.ts) / 0.3))
            w, h = self.img.size
            x0, y0, x1, y1 = x - 10, y + h * 0.62, x + w + 10, y + h * 0.40
            ImageDraw.Draw(cv).line([(x0, y0), (x0 + (x1 - x0) * p, y0 + (y1 - y0) * p)], fill=P["accent"] + (255,), width=18)


class Ranking(Layer):
    """순위 목록: 번호·이름·값(오른쪽, 강조색)·한 줄 설명. rows=[(t, 이름, 값, 설명)]."""

    def __init__(self, rows, y, row_h=170):
        self.rows, self.y, self.row_h = rows, y, row_h
        self.t0 = min(r[0] for r in rows) - 0.01

    def draw(self, cv, t):
        d = ImageDraw.Draw(cv)
        last = None
        for k, (tr, name, value, desc) in enumerate(self.rows):
            if t < tr:
                break
            y = self.y + k * self.row_h
            d.line([(M, y), (M + int((W - 2 * M) * ease_out(min(1.0, (t - tr) / 0.3))), y)], fill=P["rule"], width=2)
            a = prog(t, tr + 0.08, 0.28)
            paste(cv, T(f"{k + 1}", "heavy", 40, P["accent"], 60), (M, y + 26), alpha=a)
            paste(cv, T(name, "heavy", 48, P["ink"], 640), (M + 56, y + 22), alpha=a)
            if value:
                paste(cv, T(value, "heavy", 42, P["accent"], 300, "right"), (W - M, y + 26), alpha=a, anchor="rt")
            if desc:
                paste(cv, T(desc, "medium", 32, P["body"], W - 2 * M - 56), (M + 56, y + 92), alpha=a)
            last = y + self.row_h
        if last is not None:
            d.line([(M, last), (W - M, last)], fill=P["rule"], width=2)


class CodeBox(Layer):
    """코드 상자. lines=[(t, 한 줄, 강조?)] — 줄마다 타이핑되듯. 고정폭 글꼴엔 한글이 없을 수 있어 한글은 label 로."""

    def __init__(self, lines, y, label=None, size=40, lh=66):
        self.lines, self.y, self.label, self.size, self.lh = lines, y, label, size, lh
        self.t0 = min(ln[0] for ln in lines) - 0.2

    def draw(self, cv, t):
        h = 60 + self.lh * len(self.lines)
        a = prog(t, self.t0, 0.25)
        paste(cv, rrect(W - 2 * M, h, 14, fill=P["panel"] + (255,), outline=P["rule"] + (255,), width=2), (M, self.y), alpha=a)
        d = ImageDraw.Draw(cv)
        f = font("mono", self.size)
        for k, (tl, code, hot) in enumerate(self.lines):
            if t < tl:
                break
            n = max(1, int(len(code) * min(1.0, (t - tl) / 0.45)))
            y = self.y + 30 + k * self.lh
            if hot:
                d.rectangle([M + 8, y - 6, W - M - 8, y + self.lh - 14], fill=P["accent"] + (40,))
            d.text((M + 28, y), code[:n], font=f, fill=(P["accent"] if hot else P["ink"]) + (255,))
        if self.label:
            paste(cv, T(self.label, "medium", 28, P["mute"]), (M, self.y + h + 14), alpha=a)


class ShotCard(Layer):
    """실제 화면 캡처를 지면 폭에 맞춰 와이프로 연다. crop=(x0,y0,x1,y1), blur=[(x0,y0,x1,y1)] 가릴 곳."""

    def __init__(self, path, y, t0=0.0, crop=None, max_h=780, label=None, blur=None):
        src = Image.open(path).convert("RGB")
        for box in blur or []:
            box = tuple(box)
            src.paste(src.crop(box).filter(ImageFilter.GaussianBlur(16)), box[:2])
        if crop:
            src = src.crop(tuple(crop))
        w = W - 2 * M
        h = int(src.height * w / src.width)
        if h > max_h:
            w, h = int(src.width * max_h / src.height), max_h
        self.img = src.resize((w, h), Image.LANCZOS)
        self.y, self.t0, self.label = y, t0, label

    def draw(self, cv, t):
        if t < self.t0:
            return
        p = ease_in_out(min(1.0, (t - self.t0) / 0.45))
        w, h = self.img.size
        x = (W - w) // 2
        cv.paste(self.img.crop((0, 0, max(1, int(w * p)), h)), (x, self.y))
        paste(cv, rrect(w + 4, h + 4, 6, outline=P["ink"] + (255,), width=2), (x - 2, self.y - 2), alpha=min(1, p * 2))
        if self.label and p > 0.7:
            paste(cv, T(self.label, "medium", 28, P["mute"]), (x, self.y + h + 16), alpha=(p - 0.7) / 0.3)


class Source(Layer):
    """장면 아래 출처 줄."""

    def __init__(self, text, t0=0.3):
        self.text, self.t0 = text, t0

    def draw(self, cv, t):
        if t < self.t0:
            return
        ImageDraw.Draw(cv).line([(M, 1560), (W - M, 1560)], fill=P["rule"], width=2)
        paste(cv, T(self.text, "medium", 26, P["mute"]), (M, 1582), alpha=prog(t, self.t0, 0.3))


class Gallery(Layer):
    """화면 여러 장을 차례로 넘긴다. items=[(t, 이미지 경로, 이름표)] — 장마다 옆으로 밀려 들어온다."""

    def __init__(self, items, y=500, max_h=900):
        self.items, self.y = [], y
        for t, path, label in items:
            src = Image.open(path).convert("RGB")
            h = max_h
            w = int(src.width * h / src.height)
            self.items.append((t, src.resize((w, h), Image.LANCZOS), label))
        self.t0 = items[0][0] - 0.01

    def draw(self, cv, t):
        shown = [k for k, it in enumerate(self.items) if t >= it[0]]
        if not shown:
            return
        k = shown[-1]
        ts, img, label = self.items[k]
        p = ease_out(min(1.0, (t - ts) / 0.35))
        w, h = img.size
        x = (W - w) // 2
        if k > 0 and p < 1:  # 앞 장이 왼쪽으로 빠지고 새 장이 오른쪽에서
            prev = self.items[k - 1][1]
            cv.paste(prev, (int(x - (W * 0.9) * p), self.y))
        x += int((W * 0.9) * (1 - p))  # 이름표도 그림과 함께 들어온다
        cv.paste(img, (x, self.y))
        paste(cv, rrect(w + 4, h + 4, 6, outline=P["ink"] + (255,), width=2), (x - 2, self.y - 2))
        if label:
            tag = T(label, "heavy", 40, P["on_accent"])
            paste(cv, rrect(tag.width + 40, 70, 6, fill=P["accent"] + (255,)), (x + 24, self.y + h - 94))
            paste(cv, tag, (x + 44, self.y + h - 59), anchor="lm")
        # 몇 번째 장인지 점으로
        n = len(self.items)
        for j in range(n):
            col = P["accent"] if j == k else P["rule"]
            cx = W / 2 + (j - (n - 1) / 2) * 34
            paste(cv, rrect(16, 16, 8, fill=col + (255,)), (cx, self.y + h + 16), anchor="mm")
