# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "numpy", "playwright"]
# ///
"""카드뉴스: cards.json 하나 → 장마다 PNG(여러 크기) + PDF + 미리보기 한 장 + 릴스 mp4 + 캡션.

uv run cards.py <폴더> [--size 4:5,1:1,9:16] [--reels] [--theme neon] [--preview]
  <폴더>/cards.json 형식은 references/layouts.md
  --size     4:5(1080×1350, 인스타 피드 기본) · 1:1(1080×1080) · 9:16(1080×1920, 스토리·릴스). 여러 개면 쉼표
  --preview  미리보기(contact.jpg)만 — 휴대폰 크기로 줄여 한 장에 모은다
  --reels    9:16 으로 장마다 등장 모션을 넣은 세로 영상(reels.mp4)도 만든다 (효과음은 테마 묶음)
결과: out/<크기>/01.png …, out/cards-<크기>.pdf, out/contact.jpg, out/caption.txt, (out/reels.mp4)
글이 넘쳐 글자를 줄였거나(scale) 한 줄에 글자 하나만 남은 곳(orphan)은 끝에 '확인 필요'로 출력한다.
"""
from __future__ import annotations

import html
import io
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHORTS = HERE.parents[1] / "shorts" / "scripts"  # 같은 플러그인의 쇼츠 엔진(글꼴·테마 색·효과음)을 같이 쓴다
sys.path.insert(0, str(SHORTS))

import engine  # noqa: E402
import themes  # noqa: E402

SIZES = {"4:5": 1350, "1:1": 1080, "9:16": 1920}
ICONS = {  # 저장 · 공유 · 팔로우 (선 아이콘)
    "save": '<svg viewBox="0 0 48 48"><path d="M12 6h24v36l-12-9-12 9z"/></svg>',
    "share": '<svg viewBox="0 0 48 48"><path d="M8 24l32-16-10 32-6-12z"/><path d="M24 28l16-20"/></svg>',
    "follow": '<svg viewBox="0 0 48 48"><circle cx="20" cy="16" r="8"/><path d="M6 40c0-8 6-13 14-13s14 5 14 13"/><path d="M38 14v12M32 20h12"/></svg>',
}
ARROW = '<svg viewBox="0 0 44 24"><path d="M2 12h38M30 3l10 9-10 9" fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/></svg>'


def rich(text: str) -> str:
    """'[강조]' → <em>, '**굵게**' → <b>, 줄바꿈 유지."""
    out = []
    for m in re.finditer(r"\[([^\]]+)\]|\*\*([^*]+)\*\*|([^\[*]+|\*)", text or ""):
        if m.group(1):
            out.append(f"<em>{html.escape(m.group(1))}</em>")
        elif m.group(2):
            out.append(f"<b>{html.escape(m.group(2))}</b>")
        else:
            out.append(html.escape(m.group(3)))
    return "".join(out).replace("\n", "<br>")


def lines(text: str, d0=0.1) -> str:
    """제목: 줄마다 마스크에서 올라오게(영상) — 사진에서는 그냥 여러 줄."""
    return "".join(f'<span class="ln"><span style="--d:{d0 + k * 0.08:.2f}s">{rich(ln)}</span></span>'
                   for k, ln in enumerate((text or "").split("\n")))


def uri(folder: Path, p: str | None) -> str | None:
    if not p:
        return None
    q = Path(p).expanduser()
    q = q if q.is_absolute() else folder / q
    if not q.exists():
        raise SystemExit(f"그림 파일이 없어요: {q}")
    return q.resolve().as_uri()


def check(ok: bool) -> str:
    if ok:
        return '<svg class="ico ok" viewBox="0 0 50 50"><path d="M8 26 L20 38 L42 12"/></svg>'
    return '<svg class="ico no" viewBox="0 0 50 50"><path d="M12 12 L38 38"/><path d="M38 12 L12 38"/></svg>'


def slide_html(s: dict, i: int, n: int, deck: dict, folder: Path, h: int) -> str:
    t = s["type"]
    cls = [t]
    img = uri(folder, s.get("image"))
    body, before = [], ""
    a = lambda k: f'style="--d:{0.25 + 0.12 * k:.2f}s"'  # noqa: E731  영상용 등장 순서
    if s.get("kicker"):
        body.append(f'<div class="kicker a" {a(0)}>{html.escape(s["kicker"])}</div>' if t == "cover"
                    else f'<div class="k-line a" {a(0)}>{html.escape(s["kicker"])}</div>')
    if t == "cover":
        if img and s.get("image_mode", "bg") == "bg":
            cls.append("has-img")
            before = f'<div class="bgimg"><img src="{img}"></div>'
        elif img:
            body.insert(0, f'<div class="topimg a" style="height:{int(h * 0.3)}px"><img src="{img}"></div>')
        body.append(f'<h1 class="title" data-fit>{lines(s["title"])}</h1>')
        if s.get("big"):
            b = s["big"]
            body.append(f'<div class="big"><span class="v" data-fit>{html.escape(str(b["value"]))}</span>'
                        f'<span class="u a" {a(3)}>{html.escape(b.get("unit", ""))}</span></div>')
        if s.get("sub"):
            body.append(f'<p class="sub a" data-fit {a(4)}>{rich(s["sub"])}</p>')
    elif t == "point":
        body.append(f'<div class="no a" {a(0)}>{int(s.get("no", i)):02d}</div>')
        if img:
            body.append(f'<div class="topimg a" style="height:{int(h * 0.26)}px"><img src="{img}"></div>')
        body.append(f'<h2 class="title" data-fit>{lines(s["title"])}</h2>')
        if s.get("body"):
            body.append(f'<p class="body a" data-fit {a(3)}>{rich(s["body"])}</p>')
    elif t in ("list", "steps", "checks", "summary"):
        body.append(f'<h2 class="title" data-fit>{lines(s["title"])}</h2>')
        items = []
        for k, it in enumerate(s["items"]):
            it = it if isinstance(it, dict) else {"text": it}
            sub = f'<small>{rich(it["sub"])}</small>' if it.get("sub") else ""
            text = f'<span>{rich(it["text"])}{sub}</span>'
            lead = {"list": '<span class="dot"></span>', "steps": f'<span class="n">{k + 1}</span>',
                    "checks": check(it.get("ok", True)), "summary": f'<span class="i">{k + 1:02d}</span>'}[t]
            bad = " bad" if t == "checks" and not it.get("ok", True) else ""
            items.append(f'<div class="item a{bad}" data-fit {a(2 + k)}>{lead}{text}</div>')
        grid = f'<div class="items">{"".join(items)}</div>'
        body.append(f'<div class="box a" {a(1)}>{grid}</div>' if t == "summary" else grid)
    elif t == "stat":
        body.append(f'<div><span class="v" data-fit>{html.escape(str(s["value"]))}</span>'
                    f'<span class="u a" {a(2)}>{html.escape(s.get("unit", ""))}</span></div>')
        body.append(f'<div class="label a" data-fit {a(3)}>{rich(s["label"])}</div>')
        if s.get("note"):
            body.append(f'<p class="note a" data-fit {a(4)}>{rich(s["note"])}</p>')
    elif t == "compare":
        body.append(f'<h2 class="title" data-fit>{lines(s["title"])}</h2>')
        cols = []
        for k, side in enumerate(("left", "right")):
            c = s[side]
            mark = check(side == "right")
            lis = "".join(f'<li data-fit>{rich(x)}</li>' for x in c["items"])
            cols.append(f'<div class="col {"bad" if side == "left" else "good"} a" {a(2 + k)}><h3>{mark}{html.escape(c["label"])}</h3>'
                        f'<ul>{lis}</ul></div>')
        body.append(f'<div class="cols">{"".join(cols)}</div>')
    elif t == "quote":
        body.append('<svg class="mark-q a" viewBox="0 0 120 96"><path d="M0 96V58C0 26 16 6 48 0l6 14C36 20 28 32 27 48h25v48zm66 0V58C66 26 82 6 114 0l6 14c-18 6-26 18-27 34h25v48z"/></svg>')
        body.append(f'<blockquote class="title" data-fit>{lines(s["text"])}</blockquote>')
        if s.get("who"):
            body.append(f'<div class="who a" {a(3)}>{html.escape(s["who"])}</div>')
    elif t == "image":
        before = f'<div class="bgimg"><img src="{img}"></div>' if img else ""
        body.append(f'<div class="cap" data-fit>{lines(s.get("caption", ""))}</div>')
    elif t == "cta":
        body.append(f'<h2 class="title" data-fit>{lines(s.get("title", "저장해 두고\\n[필요할 때] 꺼내 보세요"))}</h2>')
        acts = s.get("actions", ["save", "share", "follow"])
        names = {"save": "저장", "share": "공유", "follow": "팔로우"}
        body.append('<div class="acts">' + "".join(f'<div class="act a" {a(2 + k)}>{ICONS[x]}{names[x]}</div>'
                                                  for k, x in enumerate(acts)) + '</div>')
        if deck.get("handle"):
            body.append(f'<div class="handle a" {a(6)}>{html.escape(deck["handle"])}</div>')
        if s.get("sub"):
            body.append(f'<p class="body a" data-fit {a(7)}>{rich(s["sub"])}</p>')
    else:
        raise SystemExit(f"모르는 장 종류: {t} (references/layouts.md)")
    if s.get("source"):
        body.append(f'<div class="source a" {a(8)}>{html.escape(s["source"])}</div>')

    logo = uri(folder, deck.get("logo"))
    brand = (f'<img src="{logo}">' if logo else "") + html.escape(deck.get("brand", ""))
    page = f'<span class="page"><b>{i:02d}</b> / {n:02d}</span>'
    left = html.escape(deck.get("handle", "")) if t != "cta" else ""
    right = f'<span class="swipe">넘겨 보세요 {ARROW}</span>' if t == "cover" else ""
    layers = before + deco(themes.NAME, h) if themes.NAME == "news" else deco(themes.NAME, h) + before  # 뉴스 띠는 사진 위에
    return (f'<section class="card {" ".join(cls)}" style="--h:{h}px">{layers}'
            f'<div class="frame"><div class="top"><span class="brand">{brand}</span>{page}</div>'
            f'<div class="content">{"".join(body)}</div><div class="bottom"><span>{left}</span>{right}</div></div></section>')


def deco(name, h):
    if name == "paper":
        return '<div class="deco"><div class="grain"></div><div class="rule2"></div></div>'
    if name == "neon":
        return ('<div class="deco"><div class="grid"></div><div class="glow" style="left:-300px;top:-300px;background:var(--accent)"></div>'
                f'<div class="glow" style="right:-360px;top:{h - 600}px;background:var(--accent2)"></div><div class="grain"></div></div>')
    if name == "arcade":
        return '<div class="deco"><div class="stars"></div></div>'
    if name == "calm":
        return ('<div class="deco"><div class="blob" style="right:-260px;top:-260px;width:760px;height:760px;background:var(--accent)"></div>'
                f'<div class="blob" style="left:-300px;top:{h - 520}px;width:820px;height:640px;background:var(--accent2)"></div><div class="grain"></div></div>')
    if name == "news":
        return '<div class="deco"><div class="band"></div></div>'
    return ""


def page_html(deck: dict, folder: Path, h: int, anim=False) -> str:
    slides = deck["slides"]
    cards = "".join(slide_html(s, k + 1, len(slides), deck, folder, h) for k, s in enumerate(slides))
    fonts = "".join(f'@font-face{{font-family:"P";font-weight:{w};src:url("{Path(engine.FONT_FILES[k]).resolve().as_uri()}")}}'
                    for k, w in (("heavy", 900), ("extrabold", 800), ("bold", 700), ("medium", 500)))
    fonts += f'@font-face{{font-family:"P";font-weight:600;src:url("{Path(engine.FONT_FILES["bold"]).resolve().as_uri()}")}}'
    P = themes.P
    pal = {"bg": "bg", "ink": "ink", "body": "body", "mute": "mute", "rule": "rule", "panel": "panel", "accent": "accent",
           "accent2": "accent2", "ok": "ok", "on-accent": "on_accent"}
    css_vars = ";".join(f"--{k}:rgb({P[v][0]} {P[v][1]} {P[v][2]})" for k, v in pal.items())
    if P.get("outline"):
        css_vars += f";--shade:rgb{tuple(P['outline'])}"
    mark = " mark" if themes.NAME in ("paper", "calm", "news") else ""
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{fonts}:root{{{css_vars}}}</style>'
            f'<style>{(HERE / "web" / "card.css").read_text()}</style></head>'
            f'<body class="theme-{themes.NAME}{mark}{" anim" if anim else ""}">{cards}'
            f'<script>{(HERE / "web" / "card.js").read_text()}</script></body></html>')


class Page:
    def __init__(self, path: Path, h: int):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        try:
            self.b = self.pw.chromium.launch(channel="chrome")
        except Exception:
            self.b = self.pw.chromium.launch()
        self.pg = self.b.new_page(viewport={"width": 1080, "height": h}, device_scale_factor=1)
        self.pg.goto(path.resolve().as_uri())
        self.pg.evaluate("document.fonts.ready")
        self.pg.wait_for_function("[...document.images].every(i => i.complete)")
        self.cards = self.pg.query_selector_all(".card")

    def shot(self, i: int) -> bytes:
        return self.cards[i].screenshot(type="png")

    def close(self):
        self.b.close()
        self.pw.stop()


def build(folder: Path, argv):
    deck = json.loads((folder / "cards.json").read_text())
    for bf in (folder / "brand.json", folder.parent / "brand.json"):  # 브랜드 키트: 한 번 저장해 두고 모든 세트에 쓴다
        if bf.exists():
            brand = json.loads(bf.read_text())
            if brand.get("logo") and not Path(brand["logo"]).is_absolute():
                brand["logo"] = str((bf.parent / brand["logo"]).resolve())
            deck = {**brand, **deck}
            break
    if "--theme" in argv:
        deck["theme"] = argv[argv.index("--theme") + 1]
    themes.use(deck.get("theme", "paper"), deck.get("brand", ""))
    sizes = argv[argv.index("--size") + 1].split(",") if "--size" in argv else deck.get("sizes", ["4:5"])
    out = folder / "out"
    out.mkdir(exist_ok=True)
    from PIL import Image
    problems, made = [], []
    for size in sizes:
        h = SIZES[size]
        page = out / f"_cards-{size.replace(':', 'x')}.html"
        page.write_text(page_html(deck, folder, h))
        pg = Page(page, h)
        report = pg.pg.evaluate("window.__fitReport")
        problems += [dict(r, size=size) for r in report]
        d = out / size.replace(":", "x")
        d.mkdir(exist_ok=True)
        ims = []
        for k in range(len(pg.cards)):
            png = pg.shot(k)
            (d / f"{k + 1:02d}.png").write_bytes(png)
            ims.append(Image.open(io.BytesIO(png)).convert("RGB"))
        pg.close()
        if "--preview" not in argv:
            ims[0].save(out / f"cards-{size.replace(':', 'x')}.pdf", save_all=True, append_images=ims[1:], resolution=144)
        if size == sizes[0]:  # 휴대폰 크기 미리보기: 폭 360 으로 줄여 한 장에
            w, hh = 360, int(360 * h / 1080)
            cols = min(5, len(ims))
            sheet = Image.new("RGB", (cols * (w + 16) + 16, ((len(ims) + cols - 1) // cols) * (hh + 16) + 16), (34, 34, 34))
            for k, im in enumerate(ims):
                sheet.paste(im.resize((w, hh), Image.LANCZOS), (16 + (k % cols) * (w + 16), 16 + (k // cols) * (hh + 16)))
            sheet.save(out / "contact.jpg", quality=88)
        made.append(f"{size}: {len(ims)}장 → {d}")
    if deck.get("caption") and "--preview" not in argv:
        tags = " ".join("#" + t.lstrip("#").replace(" ", "") for t in deck.get("hashtags", []))
        alt = "\n".join(f"{k + 1}. {s.get('alt', '')}" for k, s in enumerate(deck["slides"]) if s.get("alt"))
        (out / "caption.txt").write_text(deck["caption"].strip() + ("\n\n" + tags if tags else "") +
                                         ("\n\n[대체 텍스트]\n" + alt if alt else "") + "\n")
    if "--reels" in argv and "--preview" not in argv:
        reels(deck, folder, out)
        made.append(f"릴스 → {out / 'reels.mp4'}")
    print("\n".join(made))
    print(f"미리보기 → {out / 'contact.jpg'}")
    for p in problems:
        if p.get("orphan"):
            print(f"확인 필요: {p['size']} {p['slide']}장 마지막 줄에 '{p['orphan']}' 만 남음 → 문장을 줄이거나 줄바꿈(\\n)")
        else:
            print(f"확인 필요: {p['size']} {p['slide']}장 글이 넘쳐 {int(p['scale'] * 100)}%로 줄임"
                  + (" — 그래도 넘침, 글을 줄이세요" if p["overflow"] else ""))


def reels(deck, folder: Path, out: Path, per=3.2, fps=30, xf=0.35):
    """9:16 으로 장마다 등장 모션을 캡처해 이어 붙이고, 넘길 때 테마 효과음을 넣는다."""
    from PIL import Image
    import audio
    page = out / "_reels.html"
    page.write_text(page_html(deck, folder, 1920, anim=True))
    pg = Page(page, 1920)
    n = len(pg.cards)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
           "-c:v", "libx264", "-crf", "19", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out / "_reels-v.mp4")]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    prev_last = None
    events = []
    for k in range(n):
        dur = deck["slides"][k].get("seconds", per + (0.8 if k == 0 else 0))
        frames = int(dur * fps)
        events.append((sum(deck["slides"][j].get("seconds", per + (0.8 if j == 0 else 0)) for j in range(k)), "transition" if k else "cover", 0))
        last = None
        for f in range(frames):
            pg.pg.evaluate(f"__seekCard({k}, {f / fps:.4f})")
            jpg = pg.pg.screenshot(type="jpeg", quality=93)
            if prev_last is not None and f < xf * fps:  # 앞 장과 겹쳐 넘기기
                im = Image.blend(prev_last, Image.open(io.BytesIO(jpg)).convert("RGB"), (f + 1) / (xf * fps))
                buf = io.BytesIO()
                im.save(buf, "JPEG", quality=93)
                jpg = buf.getvalue()
            proc.stdin.write(jpg)
            if f == frames - 1:
                last = Image.open(io.BytesIO(jpg)).convert("RGB")
        prev_last = last
    proc.stdin.close()
    proc.wait()
    pg.close()
    total = sum(deck["slides"][j].get("seconds", per + (0.8 if j == 0 else 0)) for j in range(n))
    import numpy as np
    track = np.zeros(int((total + 0.5) * audio.SR), np.float32)
    audio.write_wav(out / "_sfx.wav", audio.mix(track, events, themes.SFX_BANK, gain_db=-10))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(out / "_reels-v.mp4"), "-i", str(out / "_sfx.wav"), "-c:v", "copy",
                    "-c:a", "aac", "-b:a", "160k", "-shortest", str(out / "reels.mp4")], check=True)
    for p in ("_reels-v.mp4", "_sfx.wav"):
        (out / p).unlink(missing_ok=True)


if __name__ == "__main__":
    args = [a for k, a in enumerate(sys.argv[1:]) if not a.startswith("--") and (k == 0 or sys.argv[k] not in ("--size", "--theme"))]
    if not args:
        sys.exit(__doc__)
    build(Path(args[0]).resolve(), sys.argv[1:])
