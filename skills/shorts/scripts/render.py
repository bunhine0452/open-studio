# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "numpy", "playwright"]
# ///
"""spec.json 하나로 쇼츠를 렌더한다.

uv run render.py <편 폴더> [--preview] [--frames 1.5,20]
  필요: <편 폴더>/spec.json, audio/narration.mp3 + narration.words.json (voice.py 가 만든다)
  --preview  장면마다 3장씩 모은 스토리보드 storyboard.jpg 만 (몇 초)
  --frames   그 시각들의 원본 크기 프레임을 _frames.jpg 로
  --theme    spec 의 테마 대신 이 테마로 (paper|neon|arcade|calm|news)
  --simple   모션 엔진(헤드리스 Chrome) 대신 가벼운 PIL 엔진으로 (Chrome 이 없을 때)
  --still    음성 없이 화면만 (대본 낱말마다 0.32초 가짜 시각) — 대본 확정 전 디자인 확인용

spec 형식은 references/spec.md. 요점:
  "theme": "paper|neon|arcade|calm|news" 또는 {"base": "neon", "colors": {"accent": "#ff8800"}, "fonts": {"heavy": "x.otf"}}
  "brand", "label", "footer" — 화면 위 채널 이름, 오른쪽 위 꼬리표, 아래 문구
  "scenes": [...] — cover · table · checks · steps · strike · ranking · code · shot · end
  장면 "from"·요소 "at" = narration 속 낱말(앞부분 일치). "[강조]" = 강조색. "caption_map" = 자막 표기.
  "sfx": {"row": "coin"} — 테마 기본 효과음을 사건별로 바꾼다(sfx.py GEN 이름).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import audio  # noqa: E402
import themes  # noqa: E402
from engine import Caption, Scene, frame_at, render  # noqa: E402

_PUNCT = re.compile(r"[\s.,!?·…'\"“”‘’()\[\]{}:;~\-—]+")


def norm(s: str) -> str:
    return _PUNCT.sub("", s)


class Anchors:
    """낱말 목록에서 앞부분 일치로 낱말 번호를 찾는다."""

    def __init__(self, words):
        self.w = [norm(x["w"]) for x in words]

    def find(self, phrase: str, start=0, end=None) -> int:
        toks = [norm(t) for t in phrase.split() if norm(t)]
        if not toks:
            raise ValueError(f"빈 앵커: {phrase!r}")
        end = len(self.w) if end is None else end
        for i in range(start, end):
            if all(i + k < len(self.w) and self.w[i + k].startswith(t) for k, t in enumerate(toks)):
                return i
        raise SystemExit(f"narration 에서 '{phrase}' 를 못 찾음 (낱말 {start}~{end}) — spec 의 from/at 을 대본 낱말 그대로 고치세요")


def display_words(words, cmap):
    """caption_map: 낱말마다 자막 표기(None=그대로, ''=앞 낱말에 합침)와 이어지는 낱말 번호."""
    disp, cont = [None] * len(words), set()
    for toks, val in sorted(((k.split(), v) for k, v in (cmap or {}).items()), key=lambda kv: -len(kv[0])):
        nt = [norm(x) for x in toks]
        for i in range(len(words) - len(toks) + 1):
            span = range(i, i + len(toks))
            if any(disp[j] is not None for j in span):
                continue
            ws = [norm(words[j]["w"]) for j in span]
            if ws[:-1] != nt[:-1] or not ws[-1].startswith(nt[-1]):
                continue
            last = words[i + len(toks) - 1]["w"].strip()
            k = last.find(toks[-1])
            disp[i] = val + (last[k + len(toks[-1]):] if k >= 0 else "")
            for j in span[1:]:
                disp[j] = ""
                cont.add(j)
    return disp, cont


def chunks_from(words, seg_starts, highlights, cmap=None, max_chars=18, min_chars=5):
    """자막 덩어리: 문장부호·장면 경계에서 끊고, 길면 반으로, 짧으면 앞에 붙인다."""
    hl = [norm(h) for h in highlights if norm(h)]
    starts = set(seg_starts)
    pieces, cur = [], []
    for i, wd in enumerate(words):
        if i in starts and cur:
            pieces.append(cur)
            cur = []
        cur.append(i)
        if wd["w"].strip().endswith((".", "?", "!", ",")):
            pieces.append(cur)
            cur = []
    if cur:
        pieces.append(cur)

    def n(ix):
        return sum(len(norm(words[i]["w"])) for i in ix)

    split = []
    for pc in pieces:
        stack = [pc]
        while stack:
            x = stack.pop(0)
            if n(x) <= max_chars or len(x) == 1:
                split.append(x)
                continue
            half, acc, cut = n(x) / 2, 0, 1
            for k, i in enumerate(x[:-1]):
                acc += len(norm(words[i]["w"]))
                if acc >= half:
                    cut = k + 1
                    break
            stack[:0] = [x[:cut], x[cut:]]
    merged = []
    for x in split:
        if merged and x[0] not in starts and (n(x) < min_chars or n(merged[-1]) < min_chars) \
                and n(merged[-1]) + n(x) <= max_chars + 8:
            merged[-1] = merged[-1] + x
        else:
            merged.append(x)
    disp, cont = display_words(words, cmap)
    for k in range(len(merged) - 1):
        while merged[k + 1] and merged[k + 1][0] in cont:
            merged[k].append(merged[k + 1].pop(0))
    merged = [x for x in merged if x]

    def label(i):
        raw = words[i]["w"].strip()
        w = (raw if disp[i] is None else disp[i]).strip().rstrip(",.")
        if not w:
            return ""
        return f"[{w}]" if any(norm(raw).startswith(h) for h in hl) else w

    return [(" ".join(s for s in (label(i) for i in x) if s), x[0], x[-1], [(label(i), i) for i in x if label(i)])
            for x in merged]


def still_words(folder, narration):
    import subprocess
    toks = (folder / "narration.txt").read_text().split()
    words, t = [], 0.2
    for tok in toks:
        words.append({"w": " " + tok, "s": round(t, 3), "e": round(t + 0.26, 3)})
        t += 0.32 + (0.35 if tok.endswith((".", "?", "!")) else 0)
    narration.parent.mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", str(t + 0.5),
                        str(narration)], check=True)
    return words


def build(folder: Path, argv=()):
    import scenes as S  # 장면 종류별 조립 (scenes.py)
    spec = json.loads((folder / "spec.json").read_text())
    if "--no-captions" in argv:  # 무자막본 (자막을 플랫폼에서 따로 달 때)
        spec["captions"] = False
    if "--theme" in argv:  # 같은 편을 다른 테마로 (갤러리·비교용)
        spec["theme"] = argv[list(argv).index("--theme") + 1]
    theme = themes.use(spec.get("theme", "paper"), spec.get("brand", "MY CHANNEL"), spec.get("label", ""),
                       spec.get("footer", "AI 음성"))
    narration = folder / "audio" / "narration.mp3"
    if "--still" in argv:
        narration = folder / "audio" / "_still.mp3"  # 음성 없이 화면만 보기: 낱말마다 0.32초로 가짜 시각을 만들고 무음 트랙을 쓴다
        words = still_words(folder, narration)
    else:
        words = json.loads(narration.with_suffix(".words.json").read_text())["words"]
    an = Anchors(words)
    sc_spec = spec["scenes"]

    starts, pos = [], 0
    for k, sc in enumerate(sc_spec):
        i = 0 if k == 0 else an.find(sc["from"], pos)
        starts.append(i)
        pos = i + 1
    segments = [(a, (starts[k + 1] - 1) if k + 1 < len(starts) else len(words) - 1) for k, a in enumerate(starts)]
    track, seg_t, W_ = audio.assemble(narration, words, segments)
    total = len(track) / audio.SR
    chunks = chunks_from(W_, starts, spec.get("highlights", []), spec.get("caption_map"))
    caps = []
    for k, (txt, a, b, toks) in enumerate(chunks):
        t1 = W_[chunks[k + 1][1]]["s"] if k + 1 < len(chunks) else total - 0.3
        caps.append(Caption(W_[a]["s"] - 0.05, min(t1 - 0.02, W_[b]["e"] + 0.6), txt))
        caps[-1].words = [(lbl, W_[i]["s"]) for lbl, i in toks]  # 낱말 자막(모션 엔진)
    bounds = [0.0] + [seg_t[i][0] - 0.12 for i in range(1, len(segments))] + [total]

    events, scenes, ctxs = [], [], []
    for i, sc in enumerate(sc_spec):
        ctx = S.Ctx(i, sc, spec, folder, segments[i], bounds[i], W_, an, events)
        ctxs.append(ctx)
        layers = S.build_scene(ctx)
        if i:
            events.append((bounds[i], "transition", 0))
        scenes.append(Scene(bounds[i], bounds[i + 1], layers))

    motion = "--simple" not in argv  # 기본은 모션 엔진(헤드리스 Chrome), --simple 은 PIL 엔진
    if motion:
        import web
        page = web.build_html(folder, spec, ctxs, bounds, caps, total)
        shot = None

        def grab(t):
            nonlocal shot
            shot = shot or web.Browser(page)
            return shot.image(t)
    else:
        def grab(t):
            return frame_at(t, scenes, caps, total, theme).convert("RGB")

    if "--frames" in argv:
        from PIL import Image
        ts = [float(x) for x in argv[list(argv).index("--frames") + 1].split(",")]
        ims = [grab(t) for t in ts]
        strip = Image.new("RGB", (1080 * len(ims), 1920))
        for k, im in enumerate(ims):
            strip.paste(im, (1080 * k, 0))
        strip.save(folder / "_frames.jpg", quality=88)
        if motion and shot:
            shot.close()
        print(folder / "_frames.jpg")
        return
    if "--preview" in argv:
        from PIL import Image
        shots = [grab(s.t0 + (s.t1 - s.t0) * f).resize((360, 640)) for s in scenes for f in (0.35, 0.7, 0.97)]
        sheet = Image.new("RGB", (360 * 6, 640 * ((len(shots) + 5) // 6)))
        for k, im in enumerate(shots):
            sheet.paste(im, ((k % 6) * 360, (k // 6) * 640))
        sheet.save(folder / "storyboard.jpg", quality=85)
        if motion and shot:
            shot.close()
        print(folder / "storyboard.jpg", round(total, 2), "초")
        return
    raw, mixed = folder / "audio" / "_mix.wav", folder / "audio" / "_mix-norm.wav"
    full = audio.mix(track.copy(), events, themes.SFX_BANK, spec.get("sfx"))
    if spec.get("bgm"):  # 코드로 합성한 배경음악, 말하는 동안 자동으로 줄어든다
        import music
        bg = spec["bgm"] if isinstance(spec["bgm"], dict) else {"style": spec["bgm"]}
        bed = music.bed(total, bg.get("style", "pop"), bg.get("bpm"), bg.get("gain", -14), voice=track)
        n = min(len(full), len(bed))
        full[:n] += bed[:n]
    audio.write_wav(raw, full)
    audio.loudnorm(raw, mixed)
    audio.srt(caps, folder / "captions.srt")
    out = folder / f"{folder.name}{'-nocap' if spec.get('captions') is False else ''}.mp4"
    if motion:
        web.render(page, total, mixed, out)
    else:
        render(scenes, caps, total, out, mixed, theme)
    raw.unlink(missing_ok=True)
    mixed.unlink(missing_ok=True)
    print(out, round(total, 2), "초")


if __name__ == "__main__":
    flags_with_value = {"--frames", "--theme"}
    argv = sys.argv[1:]
    args = [a for k, a in enumerate(argv) if not a.startswith("--") and (k == 0 or argv[k - 1] not in flags_with_value)]
    if not args:
        sys.exit(__doc__)
    build(Path(args[0]).resolve(), sys.argv[1:])
