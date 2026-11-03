# 테마 고르기

모든 테마 공통 모션: 제목은 줄마다 마스크에서 올라오고, 자막은 말하는 낱말까지 켜지며, 표 괘선·체크·취소선은 그려지고, 큰 숫자는 스프링으로 튀어나오며 센다.
모션은 `scripts/web/style.css`(테마별 `.theme-*` 블록)에서 바꾼다.

테마 = 색 + 배경 + 장면 전환 + 채널 줄·자막 모양 + 표지 그림 + 효과음 묶음. 효과음은 전부 코드로 합성한다(음원 파일·라이선스 없음).

| 테마 | 화면 | 장면 전환 | 효과음 | 어울리는 주제 |
|---|---|---|---|---|
| `paper` 지면 | 밝은 종이 결, 빨강 강조, 강조어 형광펜 | 새 페이지가 밀려 들어와 덮기 | 종이 넘김 · 연필 톡 · 책상 툭 · 펜 긋기 | 정리·코딩 팁·리뷰·책 |
| `neon` 네온 | 흐르는 격자 바닥, 빛 번짐, 주사선, 신스웨이브 해 | 글리치(조각 밀림 + 색 갈라짐) | 글리치 · 서브 베이스 · 디지털 블립 · 레이저 | AI·보안·해킹·미래 기술 |
| `arcade` 아케이드 | 흐르는 별, CRT 줄무늬, 그림자 진 글자, 계단식 움직임 | 픽셀 박스가 열리듯 | 동전 · 점프 · 파워업 · 8비트 폭발 | 게임·퀴즈·입문·재미 |
| `calm` 차분 | 천천히 흐르는 빛, 종이 결, 언덕과 해 | 블러가 풀리며 느린 페이드 | 바람 · 물방울 · 나무 톡 · 종 | 요리·건강·여행·자기계발 |
| `news` 뉴스 | 남색 띠, 아래 흐르는 자막 띠, 지구본 선 | 빨간 막대가 훑으며 새 화면 | 방송 스팅어 · 타자기 · 셔터 · 도장 | 속보·경제·정책·생활 정보 |

주제가 두 가지에 걸치면 시청자가 느낄 분위기로 고른다(예: "AI 요리 앱" → 요리 영상이면 calm, 기술 소개면 neon).

## 사용자 테마 (내 채널 색·글꼴)

```json
"theme": {
  "base": "calm",
  "colors": {"bg": "#14302a", "ink": "#f4efe1", "accent": "#f2b544", "accent2": "#ef7d57",
             "body": "#cfd9cd", "mute": "#8da69b", "rule": "#2d4b44", "panel": "#1c3a33", "ok": "#9ad17e", "on_accent": "#14302a"},
  "fonts": {"heavy": "fonts/MyBrand-Black.ttf", "medium": "fonts/MyBrand-Regular.ttf"},
  "sfx": "arcade"
}
```
- `base` 가 배경 무늬·전환·자막 모양을 정하고, `colors` 가 색을 덮어쓴다. 색 이름: bg(배경) ink(제목) body(본문) mute(보조) rule(괘선) panel(코드·그림 판) accent(강조) accent2(보조 강조) ok(체크) on_accent(강조색 위 글자) glow(네온 빛).
- `fonts` 굵기 이름: heavy(제목·숫자·자막) extrabold bold(본문) medium(보조·출처). 한글이 들어 있는 글꼴이어야 한다.
- `sfx` 는 효과음 묶음만 다른 테마 것으로.
- 대비 확인: 밝은 배경엔 어두운 ink, 어두운 배경엔 밝은 ink. 강조색 글자가 배경과 4.5:1 이상인지 본다.
- `brand`(왼쪽 위 채널 이름)·`label`(오른쪽 위)·`footer`(아래 문구)로 채널 표시를 바꾼다.

## 효과음 사건과 이름

사건: `transition`(장면 전환) `cover`(표지) `hit`(큰 숫자) `row`(표·순위 한 줄) `ok` `no`(체크 ✓ ✕) `step` `strike` `type`(코드 한 줄) `shot`(캡처) `end`(끝 카드).
spec `"sfx": {"row": "drop", "transition": "swoosh"}` 로 사건별로 바꾸고, gallery 장면은 장마다 `"sound"` 를 준다.

| 묶음 | 이름 |
|---|---|
| 지면 | page pencil desk pen_strike slide |
| 네온 | glitch sub_hit blip err_buzz zap key scan riser |
| 아케이드 | jump powerup coin bump explode select fanfare |
| 차분 | breeze bell drop wood brush chime |
| 뉴스 | swoosh stinger tick stamp typewriter shutter |

같은 소리가 기계처럼 반복되지 않게 사건마다 결·음높이가 조금씩 달라진다. 소리를 더하려면 `scripts/sfx.py` 에 numpy 함수를 쓰고 `GEN` 에 넣는다.

## 새 테마 더하기
`scripts/themes.py`: `PALETTES` 에 색, `background()`·`hero()`·`Theme.transition()`·`Theme.overlay()` 에 `NAME == "새이름"` 갈래, `scripts/sfx.py` `BANKS` 에 사건→소리 표. `render.py <예시> --still --preview --theme 새이름` 으로 확인.
