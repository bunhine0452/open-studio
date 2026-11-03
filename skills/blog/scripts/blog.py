# /// script
# requires-python = ">=3.10"
# dependencies = ["markdown>=3.5", "pillow", "numpy", "playwright", "requests"]
# ///
"""블로그 글 도우미: post.md 하나 → 점검(표절·문체·과장·키워드 과다·길이·구조) → 붙여 넣기용 HTML·썸네일 → (선택) 워드프레스 초안.

uv run blog.py check <폴더>            점검만
uv run blog.py build <폴더>            점검 + out/post.html(브라우저로 열어 전체 복사 → 네이버·티스토리 편집기에 붙여 넣기)
                                       + out/thumb-1200x630.png · out/thumb-1000x1000.png + out/post.md(마크다운 그대로)
uv run blog.py wp <폴더>               워드프레스에 '초안'으로 올린다 (환경 변수 WP_URL, WP_USER, WP_APP_PASSWORD — 응용 프로그램 비밀번호)
post.md 앞머리(frontmatter): title, description, keyword, tags[], thumbnail{title, sub, theme}, sources[{title, url, file}]
sources 의 file 은 원문 텍스트를 저장한 파일(sources/01.txt). 표절 점검은 이 원문과 본문을 글자 단위로 비교한다.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SHORTS = HERE.parents[1] / "shorts" / "scripts"
sys.path.insert(0, str(SHORTS))


def read_post(folder: Path):
    text = (folder / "post.md").read_text()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        raise SystemExit("post.md 맨 위에 --- 로 감싼 앞머리(JSON)가 필요해요 (references/post.md)")
    meta = json.loads(m.group(1))
    return meta, m.group(2).strip()


def plain(md: str) -> str:
    t = re.sub(r"```.*?```", "", md, flags=re.S)
    t = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", t)
    t = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", t)
    return re.sub(r"[#>*_`|-]", " ", t)


# ---------- 점검 ----------
def check(folder: Path, meta: dict, body: str) -> list[str]:
    from speakable import lint
    out = []
    txt = plain(body)
    n = len(re.sub(r"\s", "", txt))
    if n < 1200:
        out.append(f"길이: 공백 빼고 {n}자 — 정보 글은 1,500~3,000자가 검색에 유리해요")
    if n > 6000:
        out.append(f"길이: {n}자 — 너무 길면 두 편으로 나누세요")
    kw = meta.get("keyword", "")
    if kw:
        cnt = txt.count(kw)
        if cnt == 0:
            out.append(f"키워드 '{kw}' 가 본문에 없어요")
        elif cnt > max(7, n // 250):
            out.append(f"키워드 '{kw}' {cnt}번 — 같은 말을 너무 자주 쓰면 어뷰징으로 보여요. 300자에 한 번 정도로")
        if kw not in meta.get("title", ""):
            out.append(f"제목에 키워드 '{kw}' 가 없어요")
    t = meta.get("title", "")
    if not 15 <= len(t) <= 40:
        out.append(f"제목 {len(t)}자 — 검색 결과에서 잘리지 않게 15~40자")
    d = meta.get("description", "")
    if not 50 <= len(d) <= 160:
        out.append(f"요약(description) {len(d)}자 — 50~160자")
    h2 = re.findall(r"^## ", body, re.M)
    if len(h2) < 3:
        out.append(f"소제목(##)이 {len(h2)}개 — 세 개 이상으로 나누면 읽기 쉽고 검색에도 좋아요")
    prose = plain("\n".join(l for l in body.splitlines() if not l.lstrip().startswith("|")))
    for line in re.split(r"(?<=[.!?요다])\s", prose):
        if len(line.strip()) > 120:
            out.append(f"긴 문장 → 쪼개기: {line.strip()[:30]}…")
    imgs = re.findall(r"!\[([^\]]*)\]\(([^)]*)\)", body)
    for alt, src in imgs:
        if not alt.strip():
            out.append(f"그림 대체 텍스트 없음: {src}")
    out += [f"문체: {x}" for x in lint(txt)]
    sys.path.insert(0, str(HERE.parents[1] / "detailpage" / "scripts"))
    from detail import RISKY
    for pat, why in RISKY:
        hits = sorted(set(mm.group(0) for mm in re.finditer(pat, txt)))
        if hits:
            out.append(f"광고 문구: {', '.join(hits)} → {why}")
    out += plagiarism(folder, meta, txt)
    if not meta.get("sources"):
        out.append("출처(sources)가 없어요 — 숫자·사실에는 출처를 다세요")
    return out


def plagiarism(folder: Path, meta: dict, txt: str, run=28) -> list[str]:
    """출처 원문과 글자 단위(공백 무시)로 run 글자 이상 그대로 겹치는 곳을 찾는다."""
    norm = lambda s: re.sub(r"\s+", "", s)  # noqa: E731
    mine = norm(txt)
    out = []
    for s in meta.get("sources", []):
        f = s.get("file")
        if not f or not (folder / f).exists():
            continue
        src = norm((folder / f).read_text())
        grams = {src[i:i + run] for i in range(0, max(0, len(src) - run))}
        i, hits = 0, []
        while i < len(mine) - run:
            if mine[i:i + run] in grams:
                j = i + run
                while j < len(mine) and mine[i:j + 1] in src:
                    j += 1
                hits.append(mine[i:j])
                i = j
            else:
                i += 1
        for h in hits[:5]:
            out.append(f"표절 의심({s.get('title', f)}): '{h[:40]}…' {len(h)}자가 원문과 같아요 → 내 말로 다시 쓰고 인용이면 따옴표+출처")
    return out


# ---------- 만들기 ----------
STYLE = {  # 네이버·티스토리 편집기에 붙여 넣어도 남는 인라인 스타일
    "h2": "font-size:24px;font-weight:800;margin:44px 0 16px;line-height:1.4;",
    "h3": "font-size:19px;font-weight:700;margin:30px 0 12px;line-height:1.45;",
    "p": "font-size:17px;line-height:1.85;margin:0 0 18px;",
    "li": "font-size:17px;line-height:1.8;margin:0 0 6px;",
    "blockquote": "margin:24px 0;padding:16px 20px;border-left:4px solid {accent};background:{tint};font-size:16px;line-height:1.75;",
    "table": "border-collapse:collapse;width:100%;margin:20px 0;font-size:15px;",
    "th": "border:1px solid #ddd;padding:10px;background:{tint};font-weight:700;text-align:left;",
    "td": "border:1px solid #ddd;padding:10px;",
    "img": "max-width:100%;border-radius:8px;margin:12px 0;",
    "a": "color:{accent};text-decoration:underline;",
    "strong": "font-weight:800;",
    "pre": "background:#f4f4f2;border-radius:8px;padding:14px 16px;margin:14px 0 20px;overflow-x:auto;font-size:15px;line-height:1.6;",
    "code": "font-family:Menlo,Consolas,monospace;font-size:0.92em;background:#f4f4f2;border-radius:4px;padding:1px 5px;",
}


def build(folder: Path, meta: dict, body: str):
    import markdown
    import themes
    out = folder / "out"
    out.mkdir(exist_ok=True)
    themes.use(meta.get("thumbnail", {}).get("theme", "paper"))
    P = themes.P
    accent = "#%02x%02x%02x" % P["accent"]
    tint = "#%02x%02x%02x" % tuple(int(255 - (255 - c) * 0.1) for c in P["accent"])
    h = markdown.markdown(body, extensions=["tables", "fenced_code"])
    for tag, st in STYLE.items():
        st = st.format(accent=accent, tint=tint)
        h = re.sub(rf"<{tag}(\s|>)", lambda m, t=tag, s=st: f'<{t} style="{s}"' + m.group(1), h)
    # 그림 경로를 절대 경로로 (브라우저 미리보기용)
    h = re.sub(r'src="(?!https?:|file:)([^"]+)"', lambda m: f'src="{(folder / m.group(1)).resolve().as_uri()}"', h)
    srcs = "".join(f'<li style="{STYLE["li"]}"><a style="{STYLE["a"].format(accent=accent)}" href="{html.escape(s["url"])}">{html.escape(s["title"])}</a></li>'
                   for s in meta.get("sources", []) if s.get("url"))
    if srcs:
        h += f'<h3 style="{STYLE["h3"]}">출처</h3><ul>{srcs}</ul>'
    page = (f'<!doctype html><html><head><meta charset="utf-8"><title>{html.escape(meta["title"])}</title>'
            '<style>body{max-width:720px;margin:40px auto;padding:0 20px;font-family:Pretendard,system-ui,sans-serif;color:#222;word-break:keep-all}'
            '.tip{background:#fff7d6;border:1px solid #f0d77a;padding:14px 16px;border-radius:8px;font-size:14px;margin-bottom:30px}</style></head><body>'
            '<div class="tip">이 안내 상자 아래부터 끝까지 드래그(또는 ⌘A)해 복사한 뒤 블로그 편집기에 붙여 넣으세요. 그림은 편집기에서 한 번 더 올려야 할 수 있어요.</div>'
            f'<h1 style="font-size:30px;font-weight:900;line-height:1.35;margin:0 0 20px">{html.escape(meta["title"])}</h1>{h}</body></html>')
    (out / "post.html").write_text(page)
    (out / "post.md").write_text(f"# {meta['title']}\n\n{body}\n")
    (out / "meta.txt").write_text(
        f"제목: {meta['title']}\n제목 후보: {' / '.join(meta.get('title_options', []))}\n요약: {meta.get('description', '')}\n"
        f"태그: {', '.join(meta.get('tags', []))}\n")
    thumbs(meta, out, P)
    print(f"붙여 넣기용 → {out / 'post.html'}\n마크다운 → {out / 'post.md'}\n썸네일 → {out / 'thumb-1200x630.png'}, {out / 'thumb-1000x1000.png'}\n제목·요약·태그 → {out / 'meta.txt'}")


def thumbs(meta: dict, out: Path, P: dict):
    import engine
    from playwright.sync_api import sync_playwright
    th = meta.get("thumbnail", {})
    title = th.get("title", meta["title"])
    sub = th.get("sub", "")
    css = lambda c: "rgb(%d %d %d)" % c  # noqa: E731
    fonts = "".join(f'@font-face{{font-family:"P";font-weight:{w};src:url("{Path(engine.FONT_FILES[k]).resolve().as_uri()}")}}'
                    for k, w in (("heavy", 900), ("bold", 700), ("medium", 500)))
    t = re.sub(r"\[([^\]]+)\]", r'<em>\1</em>', html.escape(title)).replace("\n", "<br>")
    with sync_playwright() as p:
        try:
            b = p.chromium.launch(channel="chrome")
        except Exception:
            b = p.chromium.launch()
        for w, hgt, size in ((1200, 630, 76), (1000, 1000, 92)):
            doc = (f'<html><head><style>{fonts}*{{margin:0;box-sizing:border-box}}body{{width:{w}px;height:{hgt}px;background:{css(P["bg"])};'
                   f'font-family:P;color:{css(P["ink"])};word-break:keep-all;display:flex;flex-direction:column;justify-content:center;padding:0 84px;position:relative;overflow:hidden}}'
                   f'.k{{font-weight:800;font-size:30px;color:{css(P["accent"])};margin-bottom:22px}}h1{{font-weight:900;font-size:{size}px;line-height:1.16;letter-spacing:-.04em;text-wrap:balance}}'
                   f'em{{font-style:normal;color:{css(P["accent"])}}}p{{font-weight:500;font-size:34px;color:{css(P["body"])};margin-top:26px}}'
                   f'.bar{{position:absolute;left:0;top:0;bottom:0;width:22px;background:{css(P["accent"])}}}</style></head>'
                   f'<body><div class="bar"></div><div class="k">{html.escape(meta.get("keyword", ""))}</div><h1>{t}</h1>'
                   + (f"<p>{html.escape(sub)}</p>" if sub else "") + "</body></html>")
            pg = b.new_page(viewport={"width": w, "height": hgt})
            f = out / f"_thumb-{w}.html"  # 파일로 열어야 로컬 글꼴을 읽는다
            f.write_text(doc)
            pg.goto(f.resolve().as_uri())
            pg.evaluate("document.fonts.ready")
            pg.screenshot(path=str(out / f"thumb-{w}x{hgt}.png"))
        b.close()


def wordpress(folder: Path, meta: dict, body: str):
    """워드프레스 REST API 로 '초안' 작성 — 공개는 사람이 관리자 화면에서 누른다."""
    import markdown
    import requests
    url, user, pw = os.environ.get("WP_URL"), os.environ.get("WP_USER"), os.environ.get("WP_APP_PASSWORD")
    if not (url and user and pw):
        raise SystemExit("WP_URL, WP_USER, WP_APP_PASSWORD(응용 프로그램 비밀번호) 환경 변수가 필요해요")
    r = requests.post(f"{url.rstrip('/')}/wp-json/wp/v2/posts", auth=(user, pw), timeout=60,
                      json={"title": meta["title"], "content": markdown.markdown(body, extensions=["tables"]),
                            "excerpt": meta.get("description", ""), "status": "draft"})
    if r.status_code >= 300:
        raise SystemExit(f"워드프레스 오류 {r.status_code}: {r.text[:200]}")
    print("초안 작성:", r.json().get("link"))


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("check", "build", "wp"):
        sys.exit(__doc__)
    folder = Path(sys.argv[2]).resolve()
    meta, body = read_post(folder)
    issues = check(folder, meta, body)
    for x in issues:
        print("확인:", x)
    print("점검 끝" if not issues else f"확인할 곳 {len(issues)}개")
    if sys.argv[1] == "build":
        build(folder, meta, body)
    elif sys.argv[1] == "wp":
        wordpress(folder, meta, body)


if __name__ == "__main__":
    main()
