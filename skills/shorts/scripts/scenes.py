"""spec 장면 하나 → 레이어 목록 + 효과음 사건. 장면 종류는 references/spec.md."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from layers import CodeBox, CountUp, Fade, Gallery, Head, Picture, Ranking, Rows, ShotCard, Source, Steps, Strike, Tag
from themes import M, P, T

W_TEXT = 1080 - 2 * M


@dataclass
class Ctx:
    i: int
    sc: dict
    spec: dict
    folder: Path
    seg: tuple
    t0: float
    words: list
    an: object
    events: list

    def at(self, phrase, default=0.05, lead=0.1):
        """이 장면 안에서 phrase 가 시작하는 장면 시각(조금 앞당김). phrase 가 없으면 default."""
        if not phrase:
            return default
        a, b = self.seg
        return max(0.0, self.words[self.an.find(phrase, a, b + 1)]["s"] - self.t0 - lead)

    def sound(self, event, local_t, step=0):
        self.events.append((self.t0 + max(0.0, local_t), event, step))

    def path(self, p):
        q = Path(p).expanduser()
        return q if q.is_absolute() else (self.folder / q)


def kicker(txt):
    return Fade(T(txt, "bold", 32, P["accent"]), (M, 198), 0.0)


def build_scene(c: Ctx) -> list:
    sc, kind = c.sc, c.sc["type"]
    L = []
    if kind == "cover":
        photo = c.path(sc["photo"]) if sc.get("photo") else None
        L += [Picture(photo, (M, 190, W_TEXT, 430), t0=-0.2, wipe=0.5), Head(sc["headline"], 0.15, y=660, size=76)]
        if sc.get("tag"):
            L.append(Tag(sc["tag"], (M + 24, 214), t0=0.35))
        big = sc.get("big")
        if big:
            pulse = c.at(big.get("at"), None, 0) if big.get("at") else None
            L.append(CountUp(int(big["value"]), (M - 12, 830), t0=0.35, prefix=big.get("prefix", ""),
                             suffix=big.get("suffix", ""), pulse_at=pulse, comma=big.get("comma")))
            if big.get("unit"):
                v = int(big["value"])
                num = f"{v:,}" if big.get("comma", v >= 10000) else str(v)
                w = T(f"{big.get('prefix', '')}{num}{big.get('suffix', '')}", "heavy", 300, P["accent"], 1000).width
                L.append(Fade(T(big["unit"], "bold", 60, P["ink"], 300), (M - 12 + w + 10, 1080), 0.9))
            c.sound("hit", pulse if pulse is not None else 0.9)
        if sc.get("deck"):
            L.append(Fade(T(sc["deck"]["text"], "medium", 46, P["body"]), (M, 1190), c.at(sc["deck"].get("at"), 1.0)))
        c.sound("cover", 0.05)
    elif kind in ("table", "checks"):
        L += [kicker(sc.get("kicker", "")), Head(sc["headline"], 0.05)]
        n = len(sc["rows"])
        row_h = (150 if n <= 4 else 120) if kind == "table" else (128 if n <= 6 else 104)
        size = (64 if n <= 4 else 54) if kind == "table" else (54 if n <= 6 else 46)
        size = sc.get("size", size)
        rows = []
        for k, r in enumerate(sc["rows"]):
            t = c.at(r.get("at"), 0.4 + 0.5 * k)
            if kind == "table":
                rows.append((t, r["left"], r.get("right"), None, r.get("alert")))
                c.sound("row", t + 0.1, k)
            else:
                rows.append((t, r["text"], None, "ok" if r.get("ok") else "no", not r.get("ok")))
                c.sound("ok" if r.get("ok") else "no", t + 0.1, k)
        top = 560 if kind == "table" else 520
        L.append(Rows(rows, y=top, row_h=row_h, size=size))
        if sc.get("note"):
            L.append(Fade(T(sc["note"]["text"], "medium", 32, P["mute"]), (M, top + n * row_h + 30), c.at(sc["note"].get("at"), 1.5)))
    elif kind == "steps":
        L += [kicker(sc.get("kicker", "")), Head(sc["headline"], c.at(sc.get("headline_at"), 0.05) - 0.15, size=96)]
        items = [(c.at(s.get("at"), 0.5 + 0.5 * k, 0), s["text"]) for k, s in enumerate(sc["steps"])]
        L.append(Steps(items, y=600))
        for k, (t, _) in enumerate(items):
            c.sound("step", t, k)
    elif kind == "strike":
        L += [kicker(sc.get("kicker", "")), Head(sc["headline"], 0.05, size=96)]
        ts = c.at(sc["strike"].get("at"), 1.0, 0)
        L.append(Strike(sc["strike"]["text"], (M - 10, 600), t0=0.2, t_strike=ts, size=sc["strike"].get("size", 220)))
        c.sound("strike", ts)
        if sc.get("tag"):
            L.append(Tag(sc["tag"]["text"], (M, 940), t0=c.at(sc["tag"].get("at"), ts + 0.25, 0) + 0.25, size=44))
        if sc.get("deck"):
            L.append(Fade(T(sc["deck"]["text"], "medium", 44, P["body"], lh=1.35), (M, 1070), c.at(sc["deck"].get("at"), ts + 0.6)))
    elif kind == "ranking":
        L += [kicker(sc.get("kicker", "")), Head(sc["headline"], 0.05)]
        rows = [(c.at(r.get("at"), 0.4 + 0.6 * k), r["name"], r.get("value"), r.get("desc")) for k, r in enumerate(sc["items"])]
        L.append(Ranking(rows, y=500, row_h=170 if len(rows) <= 5 else 140))
        for k, r in enumerate(rows):
            c.sound("row", r[0] + 0.1, k)
    elif kind == "code":
        L += [kicker(sc.get("kicker", "")), Head(sc["headline"], 0.05)]
        lines = [(c.at(ln.get("at"), 0.5 + 0.5 * k, 0), ln["code"], bool(ln.get("hot"))) for k, ln in enumerate(sc["lines"])]
        L.append(CodeBox(lines, y=560, label=sc.get("label")))
        for k, (t, _, _) in enumerate(lines):
            c.sound("type", t, k)
    elif kind == "shot":
        L += [kicker(sc.get("kicker", "")), Head(sc["headline"], 0.05)]
        t = c.at(sc.get("at"), 0.3)
        L.append(ShotCard(c.path(sc["image"]), y=540, t0=t, crop=sc.get("crop"), label=sc.get("label"), blur=sc.get("blur")))
        c.sound("shot", t)
    elif kind == "gallery":
        L += [kicker(sc.get("kicker", "")), Head(sc["headline"], 0.05)]
        items = [(c.at(it.get("at"), 0.4 + 0.9 * k), c.path(it["image"]), it.get("label")) for k, it in enumerate(sc["items"])]
        items[0] = (min(items[0][0], 0.25),) + items[0][1:]  # 첫 장은 장면 시작부터 (빈 화면 없이)
        L.append(Gallery(items, y=sc.get("y", 470), max_h=sc.get("height", 860)))
        for (t, _, _), it in zip(items, sc["items"]):
            c.sound(it.get("sound", "shot"), t)  # 장마다 그 테마의 소리 (sfx.py GEN 이름)
    elif kind == "end":
        photo = c.path(sc["photo"]) if sc.get("photo") else None
        L += [Picture(photo, (M, 190, W_TEXT, 560), t0=0.0, wipe=0.45),
              Fade(T(sc.get("kicker", "오늘 할 일"), "bold", 34, P["accent"]), (M, 800), 0.2),
              Head(sc["todo"], 0.3, y=850, size=80)]
        if sc.get("cta"):
            L.append(Fade(T(sc["cta"], "medium", 40, P["body"], W_TEXT), (M, 1170), 0.8))
        if sc.get("link"):
            L.append(Fade(T(sc["link"], "heavy", 46, P["ink"], W_TEXT), (M, 1226), 0.9))
        c.sound("end", 0.3)
    else:
        raise SystemExit(f"모르는 장면 종류: {kind}")
    if sc.get("source") and kind != "end":
        L.append(Source(sc["source"], 0.3))
    return L
