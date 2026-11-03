"""모션 렌더러: spec 장면 → HTML/CSS/SVG 한 장 → 헤드리스 Chrome 이 프레임마다 시각을 맞춰 캡처 → ffmpeg.

CSS 애니메이션(마스크로 올라오는 글자, 선 그리기, 스프링, 블러, 3D 카드, 테마별 전환)은 web/style.css,
시각 맞추기와 낱말 자막은 web/runtime.js. 같은 시각이면 언제나 같은 프레임이 나온다(실시간 재생이 아니다).
Chrome(또는 `uv run playwright install chromium`)이 필요하다.
"""
from __future__ import annotations

import html
import io
import json
import re
import subprocess
from pathlib import Path

import engine
import themes
from themes import P

HERE = Path(__file__).resolve().parent / "web"


def esc_rich(text: str, md: float | None = None) -> str:
    """'[강조]' → <em>, 줄바꿈 → 줄 단위 마스크. md 가 있으면 강조 밑줄이 그 시각에 그어진다."""
    out = []
    for m in re.finditer(r"\[([^\]]+)\]|([^\[]+)", text):
        if m.group(1):
            out.append(f"<em>{html.escape(m.group(1))}</em>")
        else:
            out.append(html.escape(m.group(2)))
    return "".join(out)


def head(text, t, size=None, cls="head"):
    lines = text.split("\n")
    longest = max(len(re.sub(r"[\[\]]", "", x)) for x in lines)
    size = size or (96 if longest <= 9 and len(lines) <= 2 else 80 if longest <= 13 else 70)
    spans = "".join(f'<span class="ln"><span style="--d:{t + 0.09 * k:.3f}s">{esc_rich(ln)}</span></span>'
                    for k, ln in enumerate(lines))
    return f'<div class="{cls}" style="font-size:{size}px;--md:{t + 0.5:.3f}s">{spans}</div>'


def _rgb(c):
    return f"rgb({c[0]} {c[1]} {c[2]})"


def _file(p) -> str:
    return Path(p).resolve().as_uri()


def check_svg(ok: bool):
    if ok:
        return '<svg class="ico ok" viewBox="0 0 50 50"><path pathLength="1" d="M8 26 L20 38 L42 12"/></svg>'
    return ('<svg class="ico no" viewBox="0 0 50 50"><path pathLength="1" d="M12 12 L38 38"/>'
            '<path pathLength="1" d="M38 12 L12 38"/></svg>')


class Page:
    """장면 HTML 조각과 런타임 데이터(숫자 세기·타이핑)를 모은다."""

    def __init__(self, folder: Path):
        self.folder, self.counts, self.types, self.n = folder, [], [], 0

    def uid(self):
        self.n += 1
        return f"e{self.n}"

    def picture(self, c, photo, h, t):
        if photo:
            src = _file(c.path(photo))
        else:  # 사진이 없으면 테마 그림
            out = self.folder / "audio" / f"_hero-{themes.NAME}-{h}.png"
            out.parent.mkdir(exist_ok=True)
            themes.hero(936, h, themes.NAME).convert("RGB").save(out)
            src = _file(out)
        return f'<div class="pic" style="height:{h}px;--d:{t:.3f}s"><img src="{src}" style="--d:{t:.3f}s">'

    def scene(self, c) -> str:
        sc, kind, T0 = c.sc, c.sc["type"], c.t0
        g = lambda local: T0 + local  # noqa: E731  장면 시각 → 전체 시각
        at = lambda ph, d=0.05, lead=0.1: g(c.at(ph, d, lead))  # noqa: E731
        b = []
        if kind == "cover":
            b.append(self.picture(c, sc.get("photo"), 430, g(-0.1)))
            if sc.get("tag"):
                b.append(f'<span class="tag" style="--d:{g(0.4):.3f}s">{html.escape(sc["tag"])}</span>')
            b.append("</div>")
            b.append(f'<div style="height:40px"></div>{head(sc["headline"], g(0.15), 76)}')
            big = sc.get("big")
            if big:
                v = int(big["value"])
                comma = big.get("comma", v >= 10000)
                i = self.uid()
                t_num = g(0.35)
                self.counts.append({"id": i, "t0": t_num, "dur": 0.8, "to": v, "prefix": big.get("prefix", ""),
                                    "suffix": big.get("suffix", ""), "comma": comma})
                unit = f'<span class="unit a-fade" style="--d:{g(0.9):.3f}s">{html.escape(big.get("unit", ""))}</span>'
                b.append(f'<div class="big"><span class="num" id="{i}" style="--d:{t_num:.3f}s"></span>{unit}</div>')
            if sc.get("deck"):
                b.append(f'<div class="deck a-blur" style="--d:{at(sc["deck"].get("at"), 1.0):.3f}s">{esc_rich(sc["deck"]["text"])}</div>')
        elif kind in ("table", "checks"):
            b += [self.kicker(sc, g(0)), head(sc["headline"], g(0.05))]
            n = len(sc["rows"])
            if kind == "table":
                rh, size = (150 if n <= 4 else 120), (64 if n <= 4 else 54)
            else:
                rh, size = (128 if n <= 6 else 104), (54 if n <= 6 else 46)
            size = sc.get("size", size)
            rows = []
            for k, r in enumerate(sc["rows"]):
                t = at(r.get("at"), 0.4 + 0.5 * k)
                if kind == "table":
                    hot = " hot" if r.get("alert") else ""
                    right = f'<span class="r">{esc_rich(r["right"])}</span>' if r.get("right") else ""
                    rows.append(f'<div class="row{hot}" style="height:{rh}px;font-size:{size}px;--d:{t:.3f}s">'
                                f'<span class="l">{esc_rich(r["left"])}</span>{right}</div>')
                else:
                    hot = "" if r.get("ok") else " hot"
                    rows.append(f'<div class="row{hot}" style="height:{rh}px;font-size:{size}px;--d:{t:.3f}s">'
                                f'<span class="l">{check_svg(bool(r.get("ok")))}{esc_rich(r["text"])}</span></div>')
            b.append(f'<div class="rows">{"".join(rows)}</div>')
            if sc.get("note"):
                b.append(f'<div class="note a-fade" style="--d:{at(sc["note"].get("at"), 1.5):.3f}s">{esc_rich(sc["note"]["text"])}</div>')
        elif kind == "steps":
            b += [self.kicker(sc, g(0)), head(sc["headline"], at(sc.get("headline_at"), 0.05) - 0.15, 96)]
            items = []
            for k, s in enumerate(sc["steps"]):
                t = at(s.get("at"), 0.5 + 0.5 * k, 0)
                last = " last" if k == len(sc["steps"]) - 1 else ""
                items.append(f'<div class="step{last}" style="--d:{t:.3f}s"><span class="n">{k + 1}</span>'
                             f'<span class="t">{esc_rich(s["text"])}</span></div>')
            b.append(f'<div class="steps">{"".join(items)}</div>')
        elif kind == "strike":
            b += [self.kicker(sc, g(0)), head(sc["headline"], g(0.05), 96)]
            ts = at(sc["strike"].get("at"), 1.0, 0)
            size = sc["strike"].get("size", 220)
            b.append(f'<div class="strike" style="font-size:{size}px;--d:{g(0.2):.3f}s;--ds:{ts:.3f}s">'
                     f'{html.escape(sc["strike"]["text"])}<svg viewBox="0 0 100 40" preserveAspectRatio="none">'
                     f'<path pathLength="1" d="M0 28 C 30 24, 60 18, 100 12"/></svg></div>')
            after = []
            if sc.get("tag"):
                after.append(f'<span class="tag" style="font-size:44px;--d:{at(sc["tag"].get("at"), ts + 0.25, 0) + 0.25:.3f}s">'
                             f'{html.escape(sc["tag"]["text"])}</span>')
            if sc.get("deck"):
                after.append(f'<div class="deck a-blur" style="--d:{at(sc["deck"].get("at"), ts + 0.6):.3f}s">{esc_rich(sc["deck"]["text"])}</div>')
            b.append(f'<div class="after">{"".join(after)}</div>')
        elif kind == "ranking":
            b += [self.kicker(sc, g(0)), head(sc["headline"], g(0.05))]
            rows = []
            for k, r in enumerate(sc["items"]):
                t = at(r.get("at"), 0.4 + 0.6 * k)
                val = f'<span class="r">{html.escape(r["value"])}</span>' if r.get("value") else ""
                desc = f'<div class="desc">{esc_rich(r["desc"])}</div>' if r.get("desc") else ""
                rows.append(f'<div class="row" style="--d:{t:.3f}s"><span class="l"><span class="no">{k + 1}</span>'
                            f'<span><div class="name">{esc_rich(r["name"])}</div>{desc}</span></span>{val}</div>')
            b.append(f'<div class="rows rank">{"".join(rows)}</div>')
        elif kind == "code":
            b += [self.kicker(sc, g(0)), head(sc["headline"], g(0.05))]
            lines = []
            first = None
            for k, ln in enumerate(sc["lines"]):
                t = at(ln.get("at"), 0.5 + 0.5 * k, 0)
                first = t if first is None else first
                i = self.uid()
                self.types.append({"id": i, "t0": t, "dur": min(0.6, 0.02 * len(ln["code"]) + 0.15), "text": ln["code"]})
                hot = " hot" if ln.get("hot") else ""
                lines.append(f'<div class="line{hot}" style="--d:{t:.3f}s" id="{i}"></div>')
            b.append(f'<div class="code" style="--d:{first - 0.25:.3f}s">{"".join(lines)}</div>')
            if sc.get("label"):
                b.append(f'<div class="code-label a-fade" style="--d:{first:.3f}s">{html.escape(sc["label"])}</div>')
        elif kind == "shot":
            b += [self.kicker(sc, g(0)), head(sc["headline"], g(0.05))]
            t = at(sc.get("at"), 0.3)
            img = self._shot_image(c, sc)
            b.append(f'<div class="shot"><img src="{img}" style="--d:{t:.3f}s"></div>')
            if sc.get("label"):
                b.append(f'<div class="shot-label a-fade" style="--d:{t + 0.5:.3f}s">{html.escape(sc["label"])}</div>')
        elif kind == "gallery":
            b += [self.kicker(sc, g(0)), head(sc["headline"], g(0.05))]
            items = sc["items"]
            ts = [at(it.get("at"), 0.4 + 0.9 * k) for k, it in enumerate(items)]
            ts[0] = min(ts[0], g(0.25))
            y, h = sc.get("y", 490) - 190, sc.get("height", 860)
            cards = []
            for k, it in enumerate(items):
                dn = ts[k + 1] if k + 1 < len(items) else 1e5
                tag = f'<span class="tag">{html.escape(it["label"])}</span>' if it.get("label") else ""
                if it.get("video"):  # 카드 안에서 예시 영상이 흐른다: 프레임 그림을 runtime.js 가 시각마다 갈아 끼운다
                    d, n = self.video(c.path(it["video"]))
                    media = (f'<img class="vid" src="{_file(d / "00001.jpg")}" data-dir="{_file(d)}/" data-n="{n}" '
                             f'data-t0="{ts[k]:.3f}" data-t1="{dn + 1:.3f}" data-off="{it.get("offset", 0)}">')
                else:
                    media = f'<img src="{_file(c.path(it["image"]))}">'
                cards.append(f'<div class="card" style="height:{h}px;--d:{ts[k]:.3f}s;--dn:{dn:.3f}s">{media}{tag}</div>')
            b.append(f'<div class="gal" style="top:{y}px;height:{h}px">{"".join(cards)}</div>')
        elif kind == "end":
            b.append(self.picture(c, sc.get("photo"), 560, g(0)) + "</div>")
            b.append(f'<div class="todo-k a-fade" style="--d:{g(0.2):.3f}s">{html.escape(sc.get("kicker", "오늘 할 일"))}</div>')
            b.append(head(sc["todo"], g(0.3), 80))
            if sc.get("cta"):
                b.append(f'<div class="cta a-blur" style="--d:{g(0.8):.3f}s">{esc_rich(sc["cta"])}</div>')
            if sc.get("link"):
                b.append(f'<div class="link a-fade" style="--d:{g(0.95):.3f}s">{html.escape(sc["link"])}</div>')
        else:
            raise SystemExit(f"모르는 장면 종류: {kind}")
        src = ""
        if sc.get("source") and kind != "end":
            src = f'<div class="source" style="--d:{g(0.3):.3f}s"><span>{html.escape(sc["source"])}</span></div>'
        return f'<div class="body {kind}">{"".join(b)}</div>{src}'

    def video(self, path: Path):
        """카드용 프레임 그림(540 폭, 30fps). 브라우저 속 영상 탐색은 헤드리스에서 믿을 수 없어 그림으로 푼다."""
        d = self.folder / "audio" / f"_card-{path.stem}"
        stamp = d / ".src"
        key = f"{path.stat().st_mtime}"
        if not (stamp.exists() and stamp.read_text() == key):
            import shutil
            shutil.rmtree(d, ignore_errors=True)
            d.mkdir(parents=True)
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(path), "-vf", "fps=30,scale=540:-2", "-q:v", "4",
                            str(d / "%05d.jpg")], check=True)
            stamp.write_text(key)
        return d, len(list(d.glob("*.jpg")))

    def kicker(self, sc, t):
        return f'<div class="kicker a-fade" style="--d:{t:.3f}s">{html.escape(sc.get("kicker", ""))}</div>' if sc.get("kicker") else ""

    def _shot_image(self, c, sc):
        from PIL import Image, ImageFilter
        src = Image.open(c.path(sc["image"])).convert("RGB")
        for box in sc.get("blur") or []:
            box = tuple(box)
            src.paste(src.crop(box).filter(ImageFilter.GaussianBlur(16)), box[:2])
        if sc.get("crop"):
            src = src.crop(tuple(sc["crop"]))
        out = self.folder / "audio" / f"_shot-{self.uid()}.png"
        out.parent.mkdir(exist_ok=True)
        src.save(out)
        return _file(out)


def build_html(folder: Path, spec: dict, scene_ctxs: list, bounds: list, caps, total: float) -> Path:
    pg = Page(folder)
    secs = []
    n = len(scene_ctxs)
    for k, c in enumerate(scene_ctxs):
        t0 = bounds[k] if k else -10.0  # 첫 장면은 처음부터 보인다
        t1 = bounds[k + 1] if k + 1 < n else 1e5
        secs.append(f'<section class="scene" style="--t0:{t0:.3f}s;--t1:{t1:.3f}s">{pg.scene(c)}</section>')

    fonts = "".join(f'@font-face{{font-family:"P";font-weight:{w};src:url("{_file(engine.FONT_FILES[k])}")}}'
                    for k, w in (("heavy", 900), ("extrabold", 800), ("bold", 700), ("medium", 500)))
    pal = {"bg": "bg", "ink": "ink", "body": "body", "mute": "mute", "rule": "rule", "panel": "panel",
           "accent": "accent", "accent2": "accent2", "ok": "ok", "on-accent": "on_accent"}
    css_vars = ";".join(f"--{k}:{_rgb(P[v])}" for k, v in pal.items())
    css_vars += f";--total:{total:.3f}s;--totaln:{total:.3f}"
    if P.get("outline"):
        css_vars += f";--shade:{_rgb(P['outline'])}"
    name = themes.NAME
    bg = {"neon": '<div class="blob" style="left:-200px;top:-300px;width:900px;height:900px;background:var(--accent);opacity:.20;--dx:180px;--dy:120px"></div>'
                  '<div class="blob" style="right:-300px;top:600px;width:800px;height:800px;background:var(--accent2);opacity:.16;--dx:-160px;--dy:-140px"></div>'
                  '<div class="floor"></div><div class="scan"></div><div class="grain"></div>',
          "arcade": '<div class="stars"></div><div class="scan"></div>',
          "calm": '<div class="blob" style="right:-260px;top:-260px;width:820px;height:820px;background:var(--accent);opacity:.20;--dx:-120px;--dy:160px"></div>'
                  '<div class="blob" style="left:-300px;top:1100px;width:900px;height:700px;background:var(--accent2);opacity:.14;--dx:200px;--dy:-60px"></div>'
                  '<div class="grain"></div>',
          "paper": '<div class="grain"></div>',
          }.get(name, "")
    top = '<div class="band"></div>' if name == "news" else ""  # 장면 위·머리글 아래에 깔리는 띠
    ticker = ""
    if name == "news":
        msg = " · ".join(filter(None, [spec.get("label"), spec.get("brand"), spec.get("title")]))
        ticker = f'<div class="ticker"><span>{html.escape((msg + "   ·   ") * 4)}</span></div>'
    words = [{"t0": cp.t0, "t1": cp.t1, "w": [{"x": html.escape(x.strip("[]")), "s": s, "hl": x.startswith("[")}
                                             for x, s in cp.words]} for cp in caps]
    data = {"caps": words, "counts": pg.counts, "types": pg.types, "total": total}
    mark = " mark-on" if name in ("paper", "news", "calm") else ""
    doc = f"""<!doctype html><html><head><meta charset="utf-8"><style>{fonts}:root{{{css_vars}}}</style>
<style>{(HERE / "style.css").read_text()}</style></head>
<body class="theme-{name}{mark}"><div class="bg">{bg}</div>
<div id="stage">
{"".join(secs)}
{top}
<div class="mast"><span class="brand">{html.escape(spec.get("brand", ""))}</span><span class="label">{html.escape(spec.get("label", ""))}</span></div>
<div class="rules"><i></i><i></i><b></b></div>
<div class="cap"></div>
<div class="footer">{html.escape(spec.get("footer", "AI 음성"))}</div>
{ticker}
</div>
<script>window.__DATA={json.dumps(data, ensure_ascii=False)}</script>
<script>{(HERE / "runtime.js").read_text()}</script></body></html>"""
    out = folder / "audio" / "_motion.html"
    out.parent.mkdir(exist_ok=True)
    out.write_text(doc)
    return out


# 화면 밖·투명한 영상도 멈추지 않고 디코딩하게 (카드 속 영상)
ARGS = ["--disable-background-media-suspend", "--disable-renderer-backgrounding", "--disable-background-timer-throttling",
        "--autoplay-policy=no-user-gesture-required", "--disable-features=BackgroundVideoTrackOptimization,MediaPowerSaving"]


class Browser:
    def __init__(self, page_path: Path):
        from playwright.sync_api import sync_playwright
        self.pw = sync_playwright().start()
        try:
            self.b = self.pw.chromium.launch(channel="chrome", args=ARGS)
        except Exception:  # Chrome 이 없으면 Playwright 가 받은 Chromium
            try:
                self.b = self.pw.chromium.launch(args=ARGS)
            except Exception as e:
                self.pw.stop()
                raise SystemExit("Chrome 을 찾지 못했어요 — Chrome 을 설치하거나 `uvx playwright install chromium` "
                                 f"을 한 번 실행하세요 ({e.__class__.__name__})")
        self.pg = self.b.new_page(viewport={"width": engine.W, "height": engine.H})
        self.pg.goto(page_path.resolve().as_uri())
        self.pg.evaluate("document.fonts.ready")
        self.pg.wait_for_load_state("load")
        self.wait_media()

    def wait_media(self):
        self.pg.wait_for_function("[...document.images].every(i => i.complete)", timeout=60000)

    def frame(self, t: float, fmt="jpeg") -> bytes:
        self.pg.evaluate(f"__seek({t:.4f})")
        return self.pg.screenshot(type=fmt, quality=94) if fmt == "jpeg" else self.pg.screenshot(type=fmt)

    def image(self, t):
        from PIL import Image
        return Image.open(io.BytesIO(self.frame(t))).convert("RGB")

    def close(self):
        self.b.close()
        self.pw.stop()


def render(page_path: Path, total: float, audio_path: Path, out_path: Path, fps=30):
    br = Browser(page_path)
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "image2pipe", "-framerate", str(fps), "-c:v", "mjpeg", "-i", "-",
           "-i", str(audio_path), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "18",
           "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest", "-movflags", "+faststart",
           str(out_path)]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        n = int(total * fps + 0.999)
        for f in range(n):
            proc.stdin.write(br.frame(f / fps))
            if f % (fps * 10) == 0:
                print(f"  {f / fps:.0f}/{total:.0f}초", flush=True)
    finally:
        proc.stdin.close()
        br.close()
    if proc.wait() != 0:
        raise RuntimeError("ffmpeg 실패")
