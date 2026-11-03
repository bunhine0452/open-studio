# detail.json

```json
{
  "product": {"name": "상품명", "brand": "BRAND", "category": "생활용품"},
  "brand_color": "#5b7a62",
  "style": "clean",
  "widths": [860, 780, 1080],
  "split": 2400,
  "sections": [ { "type": "hero", … }, … ]
}
```
- 글 안 `[강조]` 는 브랜드 색(배경 대비 4.5:1 이상으로 자동 보정), `\n` 은 줄바꿈.
- 사진 경로는 폴더 기준. `cutout` 에 사진을 주면 배경을 지운 PNG 로 바꿔 쓴다(hero·closing).
- `split`: 조각 하나의 최대 높이(px, 860 폭 기준). 섹션을 자르지 않고 묶는다.

## 섹션

| type | 필드 | 역할 |
|---|---|---|
| hero | title, sub, image 또는 cutout, badges[] | 첫 화면: 한 줄 약속 + 상품 + 핵심 숫자 배지 |
| problem | eyebrow, title, items[] | 공감: 고객 말투의 불편 2~4개(말풍선) |
| solution | eyebrow, title, lead, image | 해결: 이 상품 한 줄 + 쓰는 사진 |
| point | no, eyebrow, title, lead, image, height?, callouts[{x, y, text}]?, facts[{value, label}]?, alt_bg? | 포인트: 사진 위 지시선(x·y 는 0~1 비율), 숫자 카드 |
| scene | image, caption, height? | 장면: 사진 한 장 꽉 차게 + 한 줄 |
| compare | eyebrow, title, columns[], rows[[…]], note? | 비교 표: 마지막 열이 우리 상품(강조) |
| specs | eyebrow, title, rows[[항목, 값]] | 사양 |
| howto | eyebrow, title, steps[{text, image?}] | 사용법 |
| reviews | eyebrow, title, items[{text, who, stars}], **source** | 실제 후기만, 어디서 받았는지 source 필수 |
| faq | eyebrow, title, items[{q, a}] | 살 때 망설이는 이유에 답 |
| notice | eyebrow, title, rows[[항목, 내용]] | 배송·교환·주의 |
| closing | title, lead, image 또는 cutout | 마무리: 진한 브랜드 면 |

## 문구 규칙 (--check 가 잡는 것)
| 표현 | 왜 |
|---|---|
| 최고·최초·유일·1위·No.1 | 표시광고법: 객관적 근거(조사 기관·기간)를 함께 |
| 100%·완벽·무조건·평생 | 입증 못 하면 부당 광고 |
| 치료·예방·완치·면역력 강화·혈당 | 의약품 오인: 일반 식품·화장품·생활용품 금지 |
| 부작용 없음·무해 | 시험 근거 필요 |
| 의사 추천·식약처 인증 | 실제 근거가 있을 때만 |
| 다이어트·체지방 | 건강기능식품 인정 내용 외 금지 |
| 주름 개선·미백 | 화장품 기능성 심사를 받은 경우만 |
| 출처 없는 후기 | 지어낸 후기는 표시광고법·전자상거래법 위반 |
점검은 1차 거르기다. 업종 규정(식품표시광고법, 화장품법, 의료기기법)은 사용자가 최종 확인한다.
