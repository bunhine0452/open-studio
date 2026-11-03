# /// script
# requires-python = ">=3.10"
# ///
"""쓴 대본(draft.txt) → 소리 나는 대로 쓴 대본(narration.txt) + 자막에 원래 표기를 되살리는 caption_map.

uv run speakable.py <편 폴더> [--write-spec]
  draft.txt  : 화면 글자처럼 쓴 대본. 영어·숫자·약어를 그대로 써도 된다 ("SSH로 3D 모델을 30일 보관")
  narration.txt : 음성 엔진에 넣을 대본 ("에스에스에이치로 쓰리디 모델을 삼십 일 보관")
  --write-spec : spec.json 의 caption_map 에 합쳐 넣는다 (자막엔 "SSH", "3D", "30일" 로 뜬다)

왜: TTS 는 영어·숫자를 엔진마다, 문맥마다 다르게 읽는다. "3D"를 "삼디"로, "SSH"를 "쉬"로 읽으면 쇼츠가 바로 싸 보인다.
개발자가 실제로 소리 내는 대로(쓰리디·에스에스에이치·픽시·제이슨) 바꿔 넣고, 자막은 원래 표기로 돌려놓는다.
사전에 없는 영어 낱말은 바꾸지 않고 '확인 필요'로 알린다 — 공식 발표 영상에서 어떻게 읽는지 찾아 READ 에 더하면 된다.
문체 점검(번역투·상투구·줄표·꾸밈 부사)도 같이 출력한다.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# ---------- 읽는 법 사전 (개발자가 실제로 소리 내는 대로) ----------
READ = {
    # 숫자 + 영문: 한자어로 읽지 않는다
    "3D": "쓰리디", "2D": "투디", "4D": "포디", "2FA": "투에프에이", "5G": "파이브지", "4G": "포지", "LTE": "엘티이",
    "4K": "포케이", "8K": "에잇케이", "M1": "엠원", "M2": "엠투", "M3": "엠쓰리", "M4": "엠포", "M5": "엠파이브",
    "B2B": "비투비", "B2C": "비투씨", "P2P": "피투피", "1:1": "일대일", "24/7": "이십사 시간 내내",
    # 원래 읽는 이름이 있는 약어
    "PXE": "픽시", "GUI": "지유아이", "SQL": "에스큐엘", "JSON": "제이슨", "YAML": "야믈", "GIF": "지프",
    "nginx": "엔진엑스", "sudo": "수도", "CLI": "씨엘아이", "API": "에이피아이", "GPT": "지피티", "SDK": "에스디케이",
    "SSH": "에스에스에이치", "AI": "에이아이", "UI": "유아이", "UX": "유엑스", "URL": "유알엘", "HTTP": "에이치티티피",
    "HTTPS": "에이치티티피에스", "TTS": "티티에스", "LLM": "엘엘엠", "MCP": "엠씨피", "RAG": "래그", "GPU": "지피유",
    "CPU": "씨피유", "NPU": "엔피유", "USB": "유에스비", "OS": "오에스", "iOS": "아이오에스", "macOS": "맥오에스",
    "PDF": "피디에프", "CSV": "씨에스브이", "HTML": "에이치티엠엘", "CSS": "씨에스에스", "DNS": "디엔에스",
    "VPN": "브이피엔", "SaaS": "사스", "OAuth": "오어스", "CUDA": "쿠다", "WASM": "와즘", "Wi-Fi": "와이파이",
    "MIT": "엠아이티", "OSS": "오에스에스", "CI": "씨아이", "PR": "피알", "IDE": "아이디이", "SEO": "에스이오",
    "npm": "엔피엠", "pnpm": "피엔피엠", "uv": "유브이", "pip": "핍", "ffmpeg": "에프에프엠펙", "VS Code": "브이에스 코드",
    ".env": "닷 엔브", "README": "리드미", "regex": "레젝스", "CRUD": "크러드", "ASCII": "아스키",
    # 제품·회사 (한국 개발 유튜브에서 흔히 부르는 대로)
    "Claude Code": "클로드 코드", "Claude": "클로드", "Anthropic": "앤트로픽", "OpenAI": "오픈에이아이",
    "ChatGPT": "챗지피티", "Gemini": "제미나이", "Google": "구글", "GitHub": "깃허브", "GitLab": "깃랩", "git": "깃",
    "Git": "깃", "reflog": "리플로그", "reset --hard": "리셋 하드", "HEAD": "헤드", "Cursor": "커서", "Copilot": "코파일럿",
    "Apple": "애플", "iPhone": "아이폰", "Mac": "맥", "Windows": "윈도우", "Linux": "리눅스", "Ubuntu": "우분투",
    "Android": "안드로이드", "Samsung": "삼성", "NVIDIA": "엔비디아", "Meta": "메타", "Microsoft": "마이크로소프트",
    "Python": "파이썬", "JavaScript": "자바스크립트", "TypeScript": "타입스크립트", "Rust": "러스트", "Go": "고",
    "React": "리액트", "Node.js": "노드제이에스", "Docker": "도커", "Kubernetes": "쿠버네티스", "YouTube": "유튜브",
    "Shorts": "쇼츠", "ElevenLabs": "일레븐랩스", "Whisper": "위스퍼", "Remotion": "리모션", "Chrome": "크롬",
    "Vercel": "버셀", "Notion": "노션", "Slack": "슬랙", "Figma": "피그마", "Pro": "프로", "Max": "맥스",
    "skill": "스킬", "Skills": "스킬", "plugin": "플러그인", "prompt": "프롬프트", "open source": "오픈소스",
    "Pretendard": "프리텐다드", "edge-tts": "엣지 티티에스",
}
LETTER = dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "에이 비 씨 디 이 에프 지 에이치 아이 제이 케이 엘 엠 엔 오 피 큐 알 에스 티 유 브이 더블유 엑스 와이 지".split()))

# ---------- 숫자 ----------
SINO = "영 일 이 삼 사 오 육 칠 팔 구".split()
NATIVE1 = ["", "한", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉"]
NATIVE10 = ["", "열", "스물", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔"]
NATIVE_COUNTERS = ("개", "명", "번", "시간", "시", "살", "가지", "줄", "편", "장", "마리", "곳", "달", "군데", "잔", "권",
                   "대", "배", "판", "단계", "글자", "문장", "사람")
SINO_COUNTERS = ("일", "월", "년", "분", "초", "원", "달러", "퍼센트", "위", "등", "층", "회", "차", "주", "개월", "점", "도", "킬로",
                 "그램", "킬로그램", "밀리리터", "리터", "미터", "센티미터", "센티", "밀리", "인치", "와트", "볼트", "칼로리",
                 "만", "억", "기가", "메가", "테라", "배속", "프레임", "픽셀", "줄당")
MONTH = {6: "유월", 10: "시월"}


def sino(n: int) -> str:
    if n == 0:
        return "영"
    out, units = "", [(10 ** 12, "조"), (10 ** 8, "억"), (10 ** 4, "만")]
    for v, name in units:
        if n >= v:
            q, n = divmod(n, v)
            out += ("" if q == 1 and name == "만" else sino(q)) + name
    for v, name in ((1000, "천"), (100, "백"), (10, "십")):
        if n >= v:
            q, n = divmod(n, v)
            out += ("" if q == 1 else SINO[q]) + name
    return out + (SINO[n] if n else "")


def native(n: int) -> str | None:
    if not 1 <= n <= 99:
        return None
    t, o = divmod(n, 10)
    if n == 20:
        return "스무"
    return NATIVE10[t] + NATIVE1[o]


def decimal(s: str) -> str:
    whole, _, frac = s.partition(".")
    return sino(int(whole)) + (" 점 " + "".join(SINO[int(d)] for d in frac) if frac else "")


def read_number(num: str, unit: str) -> tuple[str, bool]:
    """(읽는 소리, 확인 필요?)"""
    raw = num.replace(",", "")
    if "." in raw:
        return decimal(raw) + (" " + unit if unit else ""), False
    n = int(raw)
    if unit == "월" and n in MONTH:
        return MONTH[n], False
    if unit == "번째":
        return ("첫" if n == 1 else native(n) or sino(n)) + " 번째", False
    if unit and unit.startswith(NATIVE_COUNTERS) and not unit.startswith(SINO_COUNTERS):
        nat = native(n)
        if nat:
            return f"{nat} {unit}", unit == "번"  # '3번'은 횟수(세 번)인지 번호(삼 번)인지 문맥으로 확인
    return sino(n) + (" " + unit if unit else ""), False


NUM_RE = re.compile(r"(?P<cur>\$)?(?P<num>(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?)(?P<pct>%)?(?P<unit>번째|개월|시간|퍼센트|[가-힣]{0,3})")
VER_RE = re.compile(r"(?<![\d.A-Za-z])v?(\d+(?:\.\d+){2,})(?![\d.])|(?<![A-Za-z])v(\d+(?:\.\d+)?)(?![\d.])")


def convert(text: str):
    cmap, notes = {}, []

    def add(reading, original):
        if reading != original:
            cmap[reading] = original

    # 1) 사전 (긴 것부터, 영문 낱말 경계)
    for key in sorted(READ, key=len, reverse=True):
        pat = re.compile(r"(?<![A-Za-z0-9])" + re.escape(key) + r"(?![A-Za-z0-9])")
        if pat.search(text):
            text = pat.sub(READ[key], text)
            add(READ[key], key)
    # 2) 버전: 2.1.312 → 이 점 일 점 삼백십이, v2.1 → 버전 이 점 일
    def ver(m):
        if m.group(1):
            parts = m.group(1).split(".")
            r = " 점 ".join(sino(int(p)) for p in parts)
            add(r, m.group(0))
            return r
        r = "버전 " + decimal(m.group(2))
        add(r, m.group(0))
        return r
    text = VER_RE.sub(ver, text)

    # 3) 비율·점수 'N대 M' / 'N:M' → 일 대 십육 (기계를 세는 '한 대'와 헷갈리지 않게 먼저)
    def ratio(m):
        r = f"{sino(int(m.group(1)))} 대 {sino(int(m.group(2)))}"
        add(r, m.group(0))
        return r
    text = re.sub(r"(?<![\d.])(\d+)\s?(?:대|:)\s?(\d+)(?![\d.])", ratio, text)

    # 4) 숫자 + 단위
    def num(m):
        unit = m.group("unit") or ""
        if m.group("pct"):
            unit = "퍼센트" + unit
        elif m.group("cur"):
            unit = "달러" + unit
        # 조사만 붙은 경우(30을, 3이)는 단위로 보지 않는다
        word_unit = next((u for u in sorted(NATIVE_COUNTERS + SINO_COUNTERS + ("번째", "퍼센트", "달러"), key=len, reverse=True)
                          if unit.startswith(u)), "")
        rest = unit[len(word_unit):]
        r, check = read_number(m.group("num"), word_unit)
        if check:
            notes.append(f"'{m.group(0)}' → '{r}' (횟수면 그대로, 번호면 '{sino(int(m.group('num').replace(',', '')))} 번')")
        add(r, m.group(0)[: len(m.group(0)) - len(rest)])
        return r + rest
    text = NUM_RE.sub(num, text)

    # 5) 남은 영문: 대문자 약어는 한 글자씩, 나머지는 확인 필요
    def latin(m):
        w = m.group(0)
        if re.fullmatch(r"[A-Z]{2,5}", w):
            r = "".join(LETTER[c] for c in w)
            notes.append(f"'{w}' → '{r}' (글자대로 읽음 — 원래 부르는 이름이 있으면 READ 에 더하기)")
            add(r, w)
            return r
        notes.append(f"'{w}' 는 사전에 없어 그대로 둠 — 읽는 소리로 직접 바꾸기")
        return w
    text = re.sub(r"[A-Za-z][A-Za-z0-9+#.\-]*", latin, text)
    return text, cmap, notes


# ---------- 문체 점검 (AI 티 나는 표현) ----------
LINT = [
    (r"—|–", "줄표 이어 붙이기 → 문장을 나누기"), (r"[“”‘’]", "곡선 따옴표"),
    (r"[을를]\s?통해|에 의해|에 있어서|것이 가능|되어집니다|하게 됩니다", "번역투·피동 → 주어를 세우고 능동으로"),
    (r"아니라", "'X가 아니라 Y' 꾸밈 — 그냥 Y를 말하기"),
    (r"결론적으로|중요한 점은|시사하는|혁신적|획기적|놀라운", "상투구·과장"),
    (r"실제로|사실상|정말|제대로|깔끔하게|자연스럽게|확실히", "꾸밈 부사 — 빼도 뜻이 같으면 뺀다"),
    (r"핵심은|결국|정리하면|대체로", "Claude 버릇 표현"), (r"수 있습니다", "얼버무림 반복 주의"),
]


def lint(text: str) -> list[str]:
    out = []
    for pat, why in LINT:
        hits = re.findall(pat, text)
        if hits:
            out.append(f"{why}: {', '.join(sorted(set(h if isinstance(h, str) else h[0] for h in hits)))[:60]} ({len(hits)}곳)")
    for line in text.splitlines():
        if len(line) > 90 and line.count(".") <= 1:
            out.append(f"긴 문장 → 쪼개기: {line[:30]}…")
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    folder = Path(args[0]).resolve()
    draft = (folder / "draft.txt").read_text().strip()
    spoken, cmap, notes = convert(draft)
    (folder / "narration.txt").write_text(spoken + "\n")
    if "--write-spec" in sys.argv and (folder / "spec.json").exists():
        spec = json.loads((folder / "spec.json").read_text())
        spec["caption_map"] = {**cmap, **spec.get("caption_map", {})}
        (folder / "spec.json").write_text(json.dumps(spec, ensure_ascii=False, indent=2) + "\n")
    print(spoken)
    print("\ncaption_map (읽는 소리 → 자막 표기):")
    for k, v in cmap.items():
        print(f"  {k} → {v}")
    for n in notes:
        print("확인 필요:", n)
    for w in lint(draft):
        print("문체:", w)
    print(f"\n{len(spoken.replace(' ', ''))}자 (40~50초 쇼츠는 공백 빼고 230~300자 안팎)")


if __name__ == "__main__":
    main()
