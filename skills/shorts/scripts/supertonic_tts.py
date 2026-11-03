"""Supertonic 3 (Supertone, 오픈 웨이트) 한국어 음성 — 내 컴퓨터 CPU 에서 돈다. 인터넷·키·비용 없음(모델 첫 다운로드만).

추론 흐름은 Supertone 의 MIT 예제 코드(github.com/supertone-oss-archive/supertonic, py/helper.py)를 옮겨 왔다.
모델 가중치는 OpenRAIL-M(상업 이용 가능, 사용 제한 조항 있음): huggingface.co/supertone-oss-archive/supertonic-3
원 저장소는 2026-09 보관(archive) 처리됐지만 코드와 가중치는 그대로 받을 수 있다. 아래 리비전에 고정한다.

목소리: F1~F5(여), M1~M5(남). 낱말 시각은 모델이 주지 않으므로 문장마다 따로 만들고,
문장 안에서는 쉼(무음) 위치에 쉼표를 맞춘 뒤 글자 수 비율로 나눈다(자막 하이라이트에 충분한 정밀도).
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from unicodedata import normalize

import numpy as np

REPO, REV = "supertone-oss-archive/supertonic-3", "aafc6e32416a594460b32413efc49d7fe4ce6d46"
CACHE = Path.home() / ".cache" / "open-studio" / "supertonic-3"
VOICES = ("F1", "F2", "F3", "F4", "F5", "M1", "M2", "M3", "M4", "M5")


def ensure_model() -> Path:
    if not (CACHE / "onnx" / "vocoder.onnx").exists():
        from huggingface_hub import snapshot_download
        print("Supertonic 3 모델을 처음 한 번 내려받아요(약 300MB)…", flush=True)
        snapshot_download(REPO, revision=REV, local_dir=str(CACHE), allow_patterns=["onnx/*", "voice_styles/*", "LICENSE"])
    return CACHE


def _prep(text: str, lang: str) -> str:
    text = normalize("NFKD", text)
    for k, v in {"–": "-", "—": "-", "_": " ", "“": '"', "”": '"', "‘": "'", "’": "'", "[": " ", "]": " ", "|": " ",
                 "/": " ", "#": " ", "→": " "}.items():
        text = text.replace(k, v)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r" ([,.!?;:])", r"\1", text)
    if not re.search(r"[.!?;:,'\")\]}…]$", text):
        text += "."
    return f"<{lang}>{text}</{lang}>"


def _mask(lengths, max_len=None):
    max_len = max_len or int(lengths.max())
    return (np.arange(max_len) < lengths[:, None]).astype(np.float32).reshape(-1, 1, max_len)


class Supertonic:
    def __init__(self, voice: str = "F1", steps: int = 10):
        import onnxruntime as ort
        d = ensure_model()
        o = d / "onnx"
        self.cfg = json.loads((o / "tts.json").read_text())
        self.index = json.loads((o / "unicode_indexer.json").read_text())
        opts = ort.SessionOptions()
        load = lambda n: ort.InferenceSession(str(o / n), sess_options=opts, providers=["CPUExecutionProvider"])  # noqa: E731
        self.dp, self.enc, self.est, self.voc = (load(n) for n in ("duration_predictor.onnx", "text_encoder.onnx",
                                                                    "vector_estimator.onnx", "vocoder.onnx"))
        st = json.loads((d / "voice_styles" / f"{voice}.json").read_text())
        td, dd = st["style_ttl"]["dims"], st["style_dp"]["dims"]
        self.ttl = np.array(st["style_ttl"]["data"], np.float32).reshape(1, td[1], td[2])
        self.sdp = np.array(st["style_dp"]["data"], np.float32).reshape(1, dd[1], dd[2])
        self.sr = self.cfg["ae"]["sample_rate"]
        self.steps = steps

    def say(self, text: str, speed: float = 1.05, lang: str = "ko", seed: int = 0) -> np.ndarray:
        t = _prep(text, lang)
        ids = np.array([[self.index[ord(c)] for c in t]], np.int64)
        mask = _mask(np.array([ids.shape[1]], np.int64))
        dur, *_ = self.dp.run(None, {"text_ids": ids, "style_dp": self.sdp, "text_mask": mask})
        dur = dur / speed
        emb, *_ = self.enc.run(None, {"text_ids": ids, "style_ttl": self.ttl, "text_mask": mask})
        a = self.cfg["ae"]["base_chunk_size"]
        f = self.cfg["ttl"]["chunk_compress_factor"]
        wav_len = (dur * self.sr).astype(np.int64)
        lat_len = int(np.ceil(dur.max() * self.sr / (a * f)))
        rng = np.random.default_rng(seed)
        xt = rng.standard_normal((1, self.cfg["ttl"]["latent_dim"] * f, lat_len)).astype(np.float32)
        lmask = _mask((wav_len + a * f - 1) // (a * f))
        xt = xt * lmask
        total = np.array([self.steps], np.float32)
        for s in range(self.steps):
            xt, *_ = self.est.run(None, {"noisy_latent": xt, "text_emb": emb, "style_ttl": self.ttl, "text_mask": mask,
                                         "latent_mask": lmask, "current_step": np.array([s], np.float32), "total_step": total})
        wav, *_ = self.voc.run(None, {"latent": xt})
        return wav[0, : int(wav_len[0])]


def sentences(script: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", re.sub(r"\s+", " ", script).strip())
    return [p for p in parts if p]


def char_times(text: str, wav: np.ndarray, sr: int, t0: float):
    """문장 오디오 안에서 글자마다 시각을 어림한다: 쉼표 수만큼 긴 무음을 찾아 구간을 나누고, 구간 안은 글자 수 비율."""
    clean = [c for c in text if not c.isspace()]
    hop = int(sr * 0.01)
    e = np.array([np.sqrt(np.mean(wav[i:i + hop] ** 2)) for i in range(0, max(1, len(wav) - hop), hop)])
    voiced = np.where(e > max(1e-4, e.max() * 0.04))[0]
    if len(voiced) == 0:
        return [(c, t0, t0) for c in clean]
    s0, s1 = voiced[0] * 0.01, voiced[-1] * 0.01 + 0.01
    # 쉼표 자리 = 문장 안 가장 긴 무음들
    pieces = [p for p in re.split(r"(?<=,)\s*", text) if p.strip()]
    quiet = e < e.max() * 0.04
    gaps, run = [], None
    for k, q in enumerate(quiet):
        if q and run is None:
            run = k
        elif not q and run is not None:
            if run * 0.01 > s0 and k * 0.01 < s1 and k - run >= 8:
                gaps.append((k - run, run * 0.01, k * 0.01))
            run = None
    gaps = sorted(sorted(gaps, reverse=True)[: len(pieces) - 1], key=lambda g: g[1])
    bounds = [s0] + [g for _, a, b in gaps for g in (a, b)] + [s1]
    spans = [(bounds[2 * i], bounds[2 * i + 1]) for i in range(len(bounds) // 2)] if len(gaps) == len(pieces) - 1 else [(s0, s1)]
    if len(spans) != len(pieces):
        pieces, spans = [text], [(s0, s1)]
    out = []
    for p, (a, b) in zip(pieces, spans):
        cs = [c for c in p if not c.isspace()]
        n = max(1, len(cs))
        for k, c in enumerate(cs):
            out.append((c, t0 + a + (b - a) * k / n, t0 + a + (b - a) * (k + 1) / n))
    return out
