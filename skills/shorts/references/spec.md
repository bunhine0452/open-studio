# spec.json

```json
{
  "title": "유튜브 제목 (검색어 앞, 60자 안)",
  "theme": "neon",
  "brand": "SECURITY DAILY",
  "label": "보안 1분",
  "footer": "AI 음성",
  "highlights": ["십"],
  "caption_map": {"십 초": "10초"},
  "sfx": {"row": "coin"},
  "scenes": [
    {"type": "cover", "tag": "보안", "headline": "비밀번호 털렸는지\n[10초]면 확인", "big": {"value": 10, "unit": "초", "at": "십"}},
    {"type": "checks", "from": "해브", "kicker": "지금 할 일", "headline": "이메일 넣고\n[나온 곳부터]",
     "rows": [{"text": "이메일 넣어 보기", "ok": true, "at": "이메일을"}], "source": "출처 · haveibeenpwned.com"},
    {"type": "end", "from": "오늘", "todo": "이메일 하나\n[넣어 보기]", "link": "example.com/s/1"}
  ],
  "pinned": "고정 댓글", "tags": ["보안"]
}
```

- `from`(장면 시작)·`at`(요소가 나타나는 때) = narration.txt 낱말, 앞부분 일치, 1~2낱말. 첫 장면은 `from` 이 없다.
- `highlights` = 자막에서 강조색으로 칠할 낱말(narration 기준). `[대괄호]` = 화면 글자 강조.
- 경로(`photo`·`image`)는 편 폴더 기준 상대 경로나 절대 경로. `photo` 를 빼면 테마 그림이 들어간다.
- 모든 장면에 `source`(아래 출처 줄)를 달 수 있다(end 제외).

## 장면 종류

| type | 필드 | 쓰임 |
|---|---|---|
| cover | photo?, tag?, headline, big{value, prefix?, suffix?, unit?, at?, comma?}?, deck{text, at}? | 첫 장면. 큰 숫자가 0 에서 올라간다 |
| table | kicker, headline, rows[{left, right?, alert?, at}], note{text, at}?, size? | 비교·가격·사양 (2~5줄) |
| checks | kicker, headline, rows[{text, ok, at}] | 할 것 ✓ / 하지 말 것 ✕ |
| steps | kicker, headline, headline_at?, steps[{text, at}] | 순서 (마지막 단계 강조색) |
| strike | kicker, headline, strike{text, at, size?}, tag{text, at}?, deck{text, at}? | 통념·함정을 긋는다 |
| ranking | kicker, headline, items[{name, value?, desc?, at}] | 순위·추천 목록 (깃허브 저장소면 value 에 "★ 6.6k") |
| code | kicker, headline, lines[{code, hot?, at}], label? | 명령·코드 (줄당 36자, 한글 금지) |
| shot | kicker, headline, image, crop?[x0,y0,x1,y1], blur?[[x0,y0,x1,y1]], at?, label? | 실제 화면 캡처 |
| gallery | kicker, headline, items[{image, label?, at, sound?}], y?, height? | 여러 장을 차례로 넘기며 장마다 효과음 |
| end | photo?, kicker?, todo, cta?, link? | 끝 카드: 오늘 할 일 + 따라 칠 주소 |

화면 세로 배치(1920 기준): 위 0~170 채널 줄 · 190~ 장면 · 1430 자막 · 1560~ 출처 · 1650 아래 문구 · 그 아래 ~320px 는 유튜브 UI 자리라 비운다.
