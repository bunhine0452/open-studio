"""내레이션 편집: 장면 경계에서 조용한 지점을 찾아 자르고 쉼을 넣은 뒤, 테마 효과음을 섞고 음량을 맞춘다."""
from __future__ import annotations

import re
import subprocess
import wave
from pathlib import Path

import numpy as np

import sfx

SR = sfx.SR
QUIET_RMS = 0.01


def decode(path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32).copy()


def quiet_cut(src, a_end, b_start, win=0.02):
    """두 낱말 사이에서 가장 조용한 20ms 지점. 반환 (시각, 충분히 조용한가)."""
    lo, hi = max(0.0, a_end - 0.06), min(len(src) / SR, max(b_start + 0.04, a_end + 0.02))
    w = int(win * SR)
    best_t, best_r = (a_end + b_start) / 2, 1e9
    for t in np.arange(lo, hi, 0.005):
        i = int(t * SR)
        seg = src[max(0, i - w // 2):i + w // 2]
        if len(seg):
            r = float(np.sqrt((seg ** 2).mean()))
            if r < best_r:
                best_t, best_r = float(t), r
    return best_t, best_r < QUIET_RMS


def _fade(x, head, ms=12):
    n = min(len(x), int(ms / 1000 * SR))
    if n > 1:
        ramp = np.linspace(0.0, 1.0, n, dtype=x.dtype)
        if head:
            x[:n] *= ramp
        else:
            x[-n:] *= ramp[::-1]


def assemble(audio_path, words, segments, pad=0.3, lead=0.2, tail=1.6):
    """segments=[(첫 낱말, 끝 낱말)]. 장면 사이에 pad 초 쉼을 넣는다(쉼이 없는 경계는 자르지 않는다).
    반환: (오디오, 장면별 (시작, 끝) 새 시각, 낱말별 새 시각)."""
    src = decode(audio_path)
    cuts, joins = [0.0], []
    for (_, a1), (b0, _) in zip(segments, segments[1:]):
        c, quiet = quiet_cut(src, words[a1]["e"], words[b0]["s"])
        cuts.append(c)
        joins.append(quiet)
    cuts.append(len(src) / SR)
    parts, offset, seg_times, new_words = [np.zeros(int(lead * SR), np.float32)], lead, [], [None] * len(words)
    for i, (w0, w1) in enumerate(segments):
        c0, c1 = cuts[i], cuts[i + 1]
        piece = src[int(c0 * SR):int(c1 * SR)].copy()
        if i > 0 and joins[i - 1]:
            _fade(piece, head=True)
        if i < len(joins) and joins[i]:
            _fade(piece, head=False)
        parts.append(piece)
        shift = offset - c0
        for k in range(w0, w1 + 1):
            new_words[k] = {"w": words[k]["w"], "s": words[k]["s"] + shift, "e": words[k]["e"] + shift}
        seg_times.append((words[w0]["s"] + shift, words[w1]["e"] + shift))
        offset += c1 - c0
        if i < len(joins) and joins[i]:
            parts.append(np.zeros(int(pad * SR), np.float32))
            offset += pad
    parts.append(np.zeros(int(tail * SR), np.float32))
    return np.concatenate(parts), seg_times, new_words


def mix(track, events, theme, overrides=None, gain_db=-15):
    """events=[(시각, 사건, 순번)]. overrides={"row": "coin"} 이면 그 사건 소리를 바꾼다."""
    g = 10 ** (gain_db / 20)
    for k, (t, event, step) in enumerate(sorted(events)):
        s = sfx.for_event(theme, (overrides or {}).get(event, event), seed=k, step=step)
        i = int(t * SR)
        if 0 <= i < len(track):
            j = min(len(track), i + len(s))
            track[i:j] += s[: j - i] * g
    return track


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    with wave.open(str(path), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes((x * 32767).astype(np.int16).tobytes())


def loudnorm(src, dst):
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
                    "-ar", str(SR), str(dst)], check=True)


def srt(caps, path):
    def ts(x):
        h, r = divmod(x, 3600)
        m, s = divmod(r, 60)
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"
    lines = []
    for i, c in enumerate(caps, 1):
        lines += [str(i), f"{ts(c.t0)} --> {ts(c.t1)}", re.sub(r"[\[\]]", "", c.text), ""]
    Path(path).write_text("\n".join(lines), encoding="utf-8")
