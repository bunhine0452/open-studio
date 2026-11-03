# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "playwright"]
# ///
"""상세페이지: detail.json 하나 → 스마트스토어(860)·쿠팡(780)·토스(1080) 폭 긴 이미지 + 나눈 조각 + 썸네일 + HTML 원본.

uv run detail.py <폴더> [--preview] [--width 860,780,1080] [--style clean] [--check]
  <폴더>/detail.json 형식은 references/sections.md
  --preview  860 폭 한 장(preview.jpg)과 섹션 미리보기만
  --check    문구 점검(과장·의약품 오인·근거 없는 1위 등)만 하고 끝
결과: out/<폭>/full.jpg(한 장) · out/<폭>/01.jpg …(섹션 경계에서 나눈 조각) · out/thumb-white.jpg · out/thumb-styled.jpg
      out/page.html(편집 가능한 원본) · 문구 점검 결과
누끼(배경 제거)는 cutout.py 가 따로 한다 — detail.json 에서 "cutout": "photos/hero.jpg" 처럼 원본을 주면 자동으로 부른다.
"""
from __future__ import annotations

import colorsys
import html
import io
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FONTS = HERE.parents[1] / "shorts" / "fonts"
WIDTHS = {"smartstore": 860, "coupang": 780, "toss": 1080}


# ---------- 색: 브랜드 색 하나에서 나머지를 만든다 ----------
def hex2rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rgb2css(c):
    return "#" + "".join(f"{round(max(0, min(1, x)) * 255):02x}" for x in c)


def mix(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def lum(c):
    f = lambda x: x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4  # noqa: E731
    r, g, b = (f(x) for x in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = sorted((lum(a), lum(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def ink_on(bg, color, target=4.5):
    """color 를 bg 위에서 target 대비가 될 때까지 어둡게(또는 밝게) 민다."""
    h, l, s = colorsys.rgb_to_hls(*color)
    dark_bg = lum(bg) < 0.3
    for _ in range(40):
        c = colorsys.hls_to_rgb(h, l, s)
        if contrast(c, bg) >= target:
            return c
        l = min(1, l + 0.03) if dark_bg else max(0, l - 0.03)
    return colorsys.hls_to_rgb(h, l, s)


def palette(brand_hex: str, style: str) -> dict:
    B = hex2rgb(brand_hex)
    W, K = (1, 1, 1), (0.08, 0.08, 0.09)
    base = {
        "clean": dict(bg=W, ink=(.08, .08, .08), body=(.29, .29, .29), mute=(.54, .54, .54), rule=(.92, .92, .92), card=W),
        "warm": dict(bg=(.984, .969, .945), ink=(.17, .14, .125), body=(.36, .31, .28), mute=(.55, .5, .46), rule=(.925, .89, .84), card=W),
        "bold": dict(bg=W, ink=(.06, .06, .06), body=(.25, .25, .25), mute=(.5, .5, .5), rule=(.9, .9, .9), card=W),
        "dark": dict(bg=(.067, .071, .078), ink=(.95, .95, .95), body=(.78, .78, .78), mute=(.55, .55, .55), rule=(.165, .173, .19), card=(.106, .114, .13)),
        "soft": dict(bg=(1, .985, .98), ink=(.2, .17, .18), body=(.38, .34, .35), mute=(.58, .54, .55), rule=(.94, .91, .91), card=W),
    }[style]
    P = dict(base)
    P["brand"] = B
    P["brand_ink"] = ink_on(base["bg"], B)
    if style == "dark":
        P["tint"], P["tint2"] = (.09, .094, .105), mix(base["bg"], B, .28)
        P["hero_bg"] = (.09, .094, .105)
    else:
        k = {"soft": .94, "warm": .9}.get(style, .93)
        P["tint"], P["tint2"] = mix(B, W, k), mix(B, W, k - .14)
        P["hero_bg"] = mix(B, W, k + .03) if style != "bold" else mix(B, W, .8)
    h, l, s = colorsys.rgb_to_hls(*B)
    P["deep"] = colorsys.hls_to_rgb(h, .16, min(s, .5))
    P["on_deep"] = (.97, .97, .96)
    P["on_deep_accent"] = colorsys.hls_to_rgb(h, .72, min(1, s + .1))
    P["on_brand"] = W if contrast(W, B) >= 3 else K
    return {k: rgb2css(v) for k, v in P.items()}


# ---------- 문구 점검 (표시광고법·식품·화장품 광고에서 자주 걸리는 말) ----------
RISKY = [
    (r"최고|최상의|최초|유일|1위|넘버\s?원|No\.?\s?1|업계\s?1", "최상급·순위 표현: 객관적 근거(조사 기관·기간)를 같이 적어야 해요 (표시광고법)"),
    (r"100\s?%|완벽|무조건|절대|평생|영구", "단정 표현: 사실로 입증 못 하면 부당 광고가 될 수 있어요"),
    (r"치료|완치|예방|특효|질병|염증|통증\s?완화|혈압|혈당|면역력\s?(강화|증진)|항암|디톡스", "의약품 오인 표현: 일반 식품·화장품·생활용품에는 못 써요"),
    (r"부작용\s?(없|0)|무해|안전\s?100", "안전 단정: 시험 근거 없이 쓰면 안 돼요"),
    (r"의사\s?추천|약사\s?추천|전문가\s?추천|식약처\s?(인증|인정|허가)", "추천·인증 표현: 실제 인증서·근거가 있을 때만"),
    (r"다이어트|살\s?빠|체지방", "체중 감량 표현: 건강기능식품 인정 내용 외에는 못 써요"),
    (r"주름\s?(개선|제거)|미백|탈모\s?(치료|방지)", "기능성 표현: 화장품은 기능성 심사를 받은 경우만"),
]


def check_copy(spec: dict) -> list[str]:
    out = []
    text = json.dumps(spec, ensure_ascii=False)
    for pat, why in RISKY:
        hits = sorted(set(m.group(0) for m in re.finditer(pat, text)))
        if hits:
            out.append(f"{', '.join(hits)} → {why}")
    for s in spec["sections"]:
        if s["type"] == "reviews" and not s.get("source"):
            out.append("후기 섹션에 source(어디서 받은 실제 후기인지)가 없어요 — 지어낸 후기는 표시광고법·전자상거래법 위반이에요")
    return out


# ---------- HTML ----------
def rich(t):
    return re.sub(r"\[([^\]]+)\]", r"<em>\1</em>", html.escape(t or "")).replace("\n", "<br>")


class Build:
    def __init__(self, folder: Path, spec: dict):
        self.folder, self.spec = folder, spec

    def src(self, p):
        if not p:
            return None
        q = Path(p).expanduser()
        q = q if q.is_absolute() else self.folder / q
        if not q.exists():
            raise SystemExit(f"사진이 없어요: {q}")
        return q.resolve().as_uri()

    def ph(self, p, h=None, cls="ph"):
        s = self.src(p)
        style = f' style="height:{h}px"' if h else ""
        return f'<div class="{cls}"{style}><img src="{s}"></div>' if s else ""

    def head(self, s, center=False):
        eb = f'<div class="eyebrow">{html.escape(s["eyebrow"])}</div>' if s.get("eyebrow") else ""
        lead = f'<p class="lead">{rich(s["lead"])}</p>' if s.get("lead") else ""
        return f'{eb}<h2 class="t">{rich(s.get("title", ""))}</h2>{lead}'

    def section(self, s, k):
        t = s["type"]
        sp = self.spec
        if t == "hero":
            cut = self.src(s.get("cutout_png"))
            if cut:
                stage = f'<div class="stage"><div class="disc"></div><div class="floor"></div><img class="cut" src="{cut}"></div>'
            else:
                stage = f'<div class="stage">{self.ph(s.get("image"), 600)}</div>'
            badges = "".join(f'<span class="badge">{rich(b)}</span>' for b in s.get("badges", []))
            brand = html.escape(sp["product"].get("brand", ""))
            return (f'<section class="hero"><div class="brand">{brand}</div><h1>{rich(s["title"])}</h1>'
                    f'<p class="sub">{rich(s.get("sub", ""))}</p>{stage}'
                    + (f'<div class="badges">{badges}</div>' if badges else "") + "</section>")
        if t == "problem":
            bubbles = "".join(f'<div class="bubble">{rich(x)}</div>' for x in s["items"])
            return f'<section class="problem">{self.head(s, True)}<div class="bubbles">{bubbles}</div></section>'
        if t == "solution":
            return f'<section class="solution center">{self.head(s)}{self.ph(s.get("image"), 560)}</section>'
        if t == "point":
            alt = " alt" if s.get("alt_bg") else ""
            calls = ""
            for c in s.get("callouts", []):
                side = " l" if c.get("x", .5) > .6 else ""
                calls += f'<div class="callout{side}" style="left:{c["x"] * 100:.1f}%;top:{c["y"] * 100:.1f}%"><i></i><span>{html.escape(c["text"])}</span></div>'
            img = ""
            if s.get("image"):
                img = f'<div class="ph" style="height:{s.get("height", 620)}px"><img src="{self.src(s["image"])}">{calls}</div>'
            facts = ""
            if s.get("facts"):
                facts = f'<div class="facts" style="--n:{len(s["facts"])}">' + "".join(
                    f'<div class="fact"><b>{html.escape(f["value"])}</b><span>{html.escape(f["label"])}</span></div>' for f in s["facts"]) + "</div>"
            num = f'<div class="num"><b>{s.get("no", k):d}</b>POINT</div>' if s.get("no") else ""
            return f'<section class="point{alt}">{num}{self.head(s)}{img}{facts}</section>'
        if t == "compare":
            cols = s["columns"]
            th = "".join(f'<th class="{"us" if j == len(cols) - 1 else ""}">{html.escape(c)}</th>' for j, c in enumerate(cols))
            rows = "".join("<tr>" + "".join(f'<td class="{"us" if j == len(r) - 1 else ""}">{rich(str(x))}</td>' for j, x in enumerate(r)) + "</tr>"
                           for r in s["rows"])
            note = f'<p class="note">{html.escape(s["note"])}</p>' if s.get("note") else ""
            return f'<section class="compare">{self.head(s)}<table><tr>{th}</tr>{rows}</table>{note}</section>'
        if t in ("specs", "notice"):
            rows = "".join(f"<tr><td>{html.escape(str(a))}</td><td>{rich(str(b))}</td></tr>" for a, b in s["rows"])
            return f'<section class="{t}">{self.head(s)}<table>{rows}</table></section>'
        if t == "howto":
            steps = ""
            for j, st in enumerate(s["steps"]):
                img = self.ph(st.get("image"), 220)
                steps += (f'<div class="step{"" if img else " noimg"}">{img}<div><div class="k">STEP {j + 1:02d}</div>'
                          f'<p>{rich(st["text"])}</p></div></div>')
            return f'<section class="howto">{self.head(s)}<div class="steps">{steps}</div></section>'
        if t == "scene":
            return f'<section class="scene">{self.ph(s["image"], s.get("height", 900))}<div class="cap">{rich(s.get("caption", ""))}</div></section>'
        if t == "reviews":
            items = "".join(f'<div class="rv"><div class="stars">{"★" * int(r.get("stars", 5))}</div><p>{rich(r["text"])}</p>'
                            f'<div class="who">{html.escape(r.get("who", ""))}</div></div>' for r in s["items"])
            src = f'<p class="note">{html.escape(s["source"])}</p>' if s.get("source") else ""
            return f'<section class="reviews">{self.head(s)}{items}{src}</section>'
        if t == "faq":
            qs = "".join(f'<div class="q"><h3>{html.escape(q["q"])}</h3><p>{rich(q["a"])}</p></div>' for q in s["items"])
            return f'<section class="faq">{self.head(s)}{qs}</section>'
        if t == "closing":
            cut = self.src(s.get("cutout_png"))
            vis = f'<div class="cutwrap"><img src="{cut}"></div>' if cut else self.ph(s.get("image"))
            return f'<section class="closing">{self.head(s)}{vis}</section>'
        raise SystemExit(f"모르는 섹션: {t} (references/sections.md)")

    def page(self, width=860) -> str:
        sp = self.spec
        P = palette(sp.get("brand_color", "#3b6e5a"), sp.get("style", "clean"))
        css_vars = ";".join(f"--{k.replace('_', '-')}:{v}" for k, v in P.items())
        fonts = "".join(f'@font-face{{font-family:"P";font-weight:{w};src:url("{(FONTS / f).resolve().as_uri()}")}}'
                        for f, w in (("Pretendard-Black.otf", 900), ("Pretendard-ExtraBold.otf", 800),
                                     ("Pretendard-Bold.otf", 700), ("Pretendard-Bold.otf", 600), ("Pretendard-Medium.otf", 500)))
        body = "".join(self.section(s, k) for k, s in enumerate(sp["sections"], 1))
        zoom = width / 860
        return (f'<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(sp["product"]["name"])}</title>'
                f'<style>{fonts}:root{{{css_vars}}}</style><style>{(HERE / "web" / "detail.css").read_text()}</style>'
                f'<style>body{{zoom:{zoom}}}</style></head><body class="s-{sp.get("style", "clean")}">{body}</body></html>')


def cutouts(folder: Path, spec: dict):
    """hero/closing 의 "cutout": "사진" → 배경을 지운 PNG 를 만들어 cutout_png 로 넣는다(한 번 만들면 재사용)."""
    for s in spec["sections"]:
        if s.get("cutout"):
            src = folder / s["cutout"]
            dst = folder / "out" / "cutout" / (Path(s["cutout"]).stem + ".png")
            if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
                dst.parent.mkdir(parents=True, exist_ok=True)
                subprocess.run(["uv", "run", "-q", str(HERE / "cutout.py"), str(src), str(dst)], check=True)
            s["cutout_png"] = str(dst)


def shoot(page_path: Path, width: int):
    """섹션마다 따로 찍어 이어 붙인다(아주 긴 한 장을 통째로 찍으면 브라우저가 잘라 먹는다)."""
    from PIL import Image
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="chrome")
        except Exception:
            b = p.chromium.launch()
        pg = b.new_page(viewport={"width": width, "height": 1200})
        pg.goto(page_path.resolve().as_uri())
        pg.evaluate("document.fonts.ready")
        pg.wait_for_function("[...document.images].every(i => i.complete)")
        parts = [Image.open(io.BytesIO(el.screenshot(type="png"))).convert("RGB") for el in pg.query_selector_all("section")]
        b.close()
    return parts


def thumbs(folder: Path, spec: dict, out: Path):
    """대표 이미지 1000×1000: 흰 배경(오픈마켓 기본 규칙) + 브랜드 색 무대."""
    from PIL import Image, ImageDraw, ImageFilter
    hero = next((s for s in spec["sections"] if s["type"] == "hero"), None)
    if not hero:
        return
    P = palette(spec.get("brand_color", "#3b6e5a"), spec.get("style", "clean"))
    cut = hero.get("cutout_png")
    for kind, bg in (("white", "#ffffff"), ("styled", P["tint"])):
        cv = Image.new("RGB", (1000, 1000), bg)
        if cut:
            im = Image.open(cut).convert("RGBA")
            im = im.crop(im.getbbox())
            k = 760 / max(im.size)
            im = im.resize((int(im.width * k), int(im.height * k)), Image.LANCZOS)
            if kind == "styled":
                d = ImageDraw.Draw(cv)
                d.ellipse([140, 140, 860, 860], fill=P["tint2"])
            sh = Image.new("L", (1000, 1000), 0)
            ImageDraw.Draw(sh).ellipse([500 - im.width * .42, 900, 500 + im.width * .42, 940], fill=110)
            cv.paste((0, 0, 0), (0, 0), sh.filter(ImageFilter.GaussianBlur(14)))
            cv.paste(im, ((1000 - im.width) // 2, 920 - im.height), im)
        else:
            src = Image.open(folder / hero["image"]).convert("RGB")
            from PIL import ImageOps
            cv = ImageOps.fit(src, (1000, 1000), Image.LANCZOS)
        cv.save(out / f"thumb-{kind}.jpg", quality=92)


def main():
    argv = sys.argv[1:]
    args = [a for k, a in enumerate(argv) if not a.startswith("--") and (k == 0 or argv[k - 1] not in ("--width", "--style"))]
    if not args:
        sys.exit(__doc__)
    folder = Path(args[0]).resolve()
    spec = json.loads((folder / "detail.json").read_text())
    if "--style" in argv:
        spec["style"] = argv[argv.index("--style") + 1]
    issues = check_copy(spec)
    for x in issues:
        print("문구 확인:", x)
    if "--check" in argv:
        print("문구 점검 끝" if not issues else f"확인할 곳 {len(issues)}개")
        return
    out = folder / "out"
    out.mkdir(exist_ok=True)
    cutouts(folder, spec)
    widths = [int(w) for w in argv[argv.index("--width") + 1].split(",")] if "--width" in argv else spec.get("widths", [860, 780, 1080])
    if "--preview" in argv:
        widths = [860]
    from PIL import Image
    b = Build(folder, spec)
    (out / "page.html").write_text(b.page(860))
    split = int(spec.get("split", 2400))
    for w in widths:
        page = out / f"_page-{w}.html"
        page.write_text(b.page(w))
        parts = shoot(page, w)
        H = sum(p.height for p in parts)
        full = Image.new("RGB", (w, H), "white")
        y = 0
        for p in parts:
            full.paste(p, (0, y))
            y += p.height
        d = out / str(w)
        d.mkdir(exist_ok=True)
        if "--preview" in argv:
            full.resize((430, int(H * 430 / w))).save(out / "preview.jpg", quality=86)
            print(f"미리보기 → {out / 'preview.jpg'} ({w}×{H}, 섹션 {len(parts)}개)")
            return
        full.save(d / "full.jpg", quality=90, optimize=True)
        # 섹션 경계에서 나누기: 조각 높이가 split 을 넘지 않게 섹션을 묶는다
        chunks, cur = [], []
        for p in parts:
            if cur and sum(x.height for x in cur) + p.height > split:
                chunks.append(cur)
                cur = []
            cur.append(p)
        chunks.append(cur)
        for k, ch in enumerate(chunks, 1):
            im = Image.new("RGB", (w, sum(x.height for x in ch)), "white")
            yy = 0
            for x in ch:
                im.paste(x, (0, yy))
                yy += x.height
            im.save(d / f"{k:02d}.jpg", quality=90, optimize=True)
            im.save(d / f"{k:02d}.webp", quality=88)
        print(f"{w}px: 한 장 {w}×{H} → {d / 'full.jpg'} · 조각 {len(chunks)}개")
    thumbs(folder, spec, out)
    print(f"썸네일 → {out / 'thumb-white.jpg'}, {out / 'thumb-styled.jpg'} · 원본 HTML → {out / 'page.html'}")


if __name__ == "__main__":
    main()
