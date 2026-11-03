# /// script
# requires-python = ">=3.10"
# dependencies = ["edge-tts>=7", "requests"]
# ///
"""내레이션 음성 + 낱말 시각. 기본은 무료(키 없음) edge-tts.

uv run voice.py <편 폴더> [--engine edge|elevenlabs] [--voice ko-KR-SunHiNeural] [--rate +12%]
  읽는 것: <편 폴더>/narration.txt (speakable.py 를 거친, 소리 나는 대로 쓴 대본)
  만드는 것: audio/narration.mp3, audio/narration.words.json  ({"words": [{"w": " 낱말,", "s": 0.1, "e": 0.4}]})

엔진
  edge        무료, 키 없음, 인터넷 필요. 한국어 목소리: ko-KR-SunHiNeural(여) · ko-KR-InJoonNeural(남)
              · ko-KR-HyunsuMultilingualNeural(남). 말 빠르기 --rate (+0% ~ +25%, 쇼츠는 +10% 안팎)
  elevenlabs  유료 선택지. 환경 변수 ELEVENLABS_API_KEY, --voice <voice_id>, --model eleven_v3
낱말 시각은 엔진이 주는 경계(글자·낱말 시각)를 대본 글자에 맞춰 붙인다 — 받아쓰기(Whisper)가 필요 없다.

목소리 품질 (전부 무료)
  --audition  첫 문장을 한국어 목소리 3개 × 빠르기 3단계로 들어 볼 수 있게 audio/audition/ 에 만든다 → 귀로 고른다
  --polish    방송용 다듬기(기본 켜짐): 웅웅거림 자르기·낮은 울림 살짝·또렷함(3kHz) 올리기·치찰음 줄이기·가벼운 압축.
              시간은 바꾸지 않아 낱말 시각이 그대로다. 끄려면 --no-polish
  --tempo 1.1 만든 뒤 ffmpeg 로 빠르기만 올린다(음높이 유지). 엔진 빠르기보다 말투가 덜 뭉개질 때가 많다. 낱말 시각도 맞춰 줄인다
  --pitch +0Hz edge 목소리 높낮이 (-20Hz ~ +20Hz 안팎)
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import difflib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

_PUNCT = re.compile(r"[\s.,!?·…'\"“”‘’()\[\]{}:;~\-—]+")


def char_times_to_words(script: str, chars: list[tuple[str, float, float]]) -> list[dict]:
    """엔진이 준 (글자, 시작, 끝) 목록을 대본의 띄어쓰기 낱말(문장부호 포함)에 맞춘다.
    엔진이 숫자·문장부호를 다르게 쪼개도 글자 정렬(difflib)로 맞추고, 못 맞춘 글자는 앞뒤로 보간한다."""
    tokens = script.split()
    sc = [(ti, ch) for ti, tok in enumerate(tokens) for ch in _PUNCT.sub("", tok)]
    eng = [(c, s, e) for c, s, e in chars if _PUNCT.sub("", c)]
    a, b = "".join(ch for _, ch in sc), "".join(c for c, _, _ in eng)
    times: list[tuple[float, float] | None] = [None] * len(sc)
    for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            times[blk.a + k] = eng[blk.b + k][1:]
    known = [k for k, v in enumerate(times) if v]
    if not known:
        raise SystemExit("엔진 시각을 대본에 하나도 맞추지 못했어요")
    for k in range(len(times)):  # 빈 칸 보간
        if times[k] is None:
            lo = max((j for j in known if j < k), default=None)
            hi = min((j for j in known if j > k), default=None)
            if lo is None:
                times[k] = (times[hi][0], times[hi][0])
            elif hi is None:
                times[k] = (times[lo][1], times[lo][1])
            else:
                f = (k - lo) / (hi - lo)
                t = times[lo][1] + (times[hi][0] - times[lo][1]) * f
                times[k] = (t, t)
    out = []
    for ti, tok in enumerate(tokens):
        ks = [k for k, (t, _) in enumerate(sc) if t == ti]
        if not ks:  # 문장부호만 있는 토큰은 앞 낱말에 붙인다
            if out:
                out[-1]["w"] += tok
            continue
        out.append({"w": " " + tok, "s": round(times[ks[0]][0], 3), "e": round(times[ks[-1]][1], 3)})
    return out


def boundaries_to_chars(bounds):
    """낱말 경계 [(글, 시작, 길이)] → 글자마다 시각을 고르게 나눈다."""
    chars = []
    for text, s, d in bounds:
        clean = _PUNCT.sub("", text)
        for k, ch in enumerate(clean):
            chars.append((ch, s + d * k / len(clean), s + d * (k + 1) / len(clean)))
    return chars


POLISH = ("highpass=f=75,lowpass=f=13500,equalizer=f=180:t=q:w=1.0:g=1.5,equalizer=f=3200:t=q:w=1.2:g=2.5,"
          "deesser=i=0.4,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120:makeup=2")
KO_VOICES = ("ko-KR-SunHiNeural", "ko-KR-InJoonNeural", "ko-KR-HyunsuMultilingualNeural")


def post(mp3: Path, polish=True, tempo=1.0):
    """다듬기·빠르기를 ffmpeg 한 번에. 반환: 시각에 곱할 배율."""
    chain = [POLISH] if polish else []
    if abs(tempo - 1.0) > 1e-3:
        chain.append(f"atempo={tempo}")
    if not chain:
        return 1.0
    tmp = mp3.with_name(mp3.stem + "-raw.mp3")
    mp3.replace(tmp)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-af", ",".join(chain), "-c:a", "libmp3lame", "-q:a", "2",
                    str(mp3)], check=True)
    tmp.unlink()
    return 1.0 / tempo


def audition(folder: Path, script: str):
    first = re.split(r"(?<=[.?!])\s", script, maxsplit=1)[0]
    out = folder / "audio" / "audition"
    out.mkdir(parents=True, exist_ok=True)
    for v in KO_VOICES:
        for rate in ("+0%", "+10%", "+20%"):
            f = out / f"{v.split('-')[2].replace('Neural', '')}{rate.replace('%', '')}.mp3"
            edge(first, f, v, rate)
            post(f, True)
            print(f)
    print("들어 보고 마음에 드는 목소리·빠르기를 --voice / --rate 로 넘기세요")


async def _edge(script, voice, rate, out_mp3, pitch="+0Hz"):
    import edge_tts
    comm = edge_tts.Communicate(script, voice, rate=rate, pitch=pitch, boundary="WordBoundary")
    bounds = []
    with open(out_mp3, "wb") as f:
        async for ch in comm.stream():
            if ch["type"] == "audio":
                f.write(ch["data"])
            elif ch["type"] == "WordBoundary":
                bounds.append((ch["text"], ch["offset"] / 1e7, ch["duration"] / 1e7))
    return boundaries_to_chars(bounds)


def edge(script, out_mp3, voice="ko-KR-SunHiNeural", rate="+12%", pitch="+0Hz"):
    return asyncio.run(_edge(script, voice, rate, out_mp3, pitch))


def elevenlabs(script, out_mp3, voice, model="eleven_v3", speed=None):
    import requests
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise SystemExit("ELEVENLABS_API_KEY 환경 변수가 없어요 (무료로 하려면 --engine edge)")
    body = {"text": script, "model_id": model, "language_code": "ko",
            "voice_settings": {"stability": 0.5, "similarity_boost": 0.8} | ({"speed": speed} if speed else {})}
    r = requests.post(f"https://api.elevenlabs.io/v1/text-to-speech/{voice}/with-timestamps", headers={"xi-api-key": key},
                      params={"output_format": "mp3_44100_192"}, json=body, timeout=600)
    if r.status_code != 200:
        raise SystemExit(f"ElevenLabs HTTP {r.status_code}: {r.text[:300]}")
    d = r.json()
    Path(out_mp3).write_bytes(base64.b64decode(d["audio_base64"]))
    al = d.get("alignment") or d["normalized_alignment"]
    return list(zip(al["characters"], al["character_start_times_seconds"], al["character_end_times_seconds"]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder")
    ap.add_argument("--engine", default="edge", choices=["edge", "elevenlabs"])
    ap.add_argument("--voice", default=None)
    ap.add_argument("--rate", default="+12%", help="edge 말 빠르기")
    ap.add_argument("--model", default="eleven_v3")
    ap.add_argument("--speed", type=float, default=None, help="elevenlabs 말 빠르기 0.7~1.2")
    ap.add_argument("--pitch", default="+0Hz", help="edge 높낮이")
    ap.add_argument("--tempo", type=float, default=1.0, help="만든 뒤 빠르기만 올리기 (예 1.1)")
    ap.add_argument("--no-polish", action="store_true", help="방송용 다듬기 끄기")
    ap.add_argument("--audition", action="store_true", help="목소리 비교 샘플만 만들기")
    a = ap.parse_args(argv)
    folder = Path(a.folder).resolve()
    script = re.sub(r"\s+", " ", (folder / "narration.txt").read_text()).strip()
    if re.search(r"[A-Za-z0-9]", script):
        print("주의: 대본에 영어·숫자가 남아 있어요 — speakable.py 로 읽는 소리로 바꾸면 엔진마다 읽는 법이 흔들리지 않아요",
              file=sys.stderr)
    (folder / "audio").mkdir(exist_ok=True)
    if a.audition:
        return audition(folder, script)
    mp3 = folder / "audio" / "narration.mp3"
    if a.engine == "edge":
        chars = edge(script, mp3, a.voice or "ko-KR-SunHiNeural", a.rate, a.pitch)
    else:
        if not a.voice:
            raise SystemExit("--voice <ElevenLabs voice_id> 가 필요해요")
        chars = elevenlabs(script, mp3, a.voice, a.model, a.speed)
    k = post(mp3, not a.no_polish, a.tempo)
    chars = [(ch, st * k, en * k) for ch, st, en in chars]
    words = char_times_to_words(script, chars)
    (folder / "audio" / "narration.words.json").write_text(
        json.dumps({"words": words, "engine": a.engine, "voice": a.voice}, ensure_ascii=False, indent=1))
    dur = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                         str(mp3)]).decode())
    print(json.dumps({"audio": str(mp3), "seconds": round(dur, 1), "words": len(words), "engine": a.engine},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
