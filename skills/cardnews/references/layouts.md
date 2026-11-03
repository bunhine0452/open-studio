# cards.json

```json
{
  "theme": "paper",
  "brand": "MY BRAND", "handle": "@my.brand", "logo": "brand/logo.png",
  "sizes": ["4:5", "1:1", "9:16"],
  "slides": [ { "type": "cover", "kicker": "…", "title": "…\n[강조]", "sub": "…", "alt": "…" }, … ],
  "caption": "인스타 캡션", "hashtags": ["카드뉴스", "…"]
}
```
글 안의 `[강조]` 는 강조색(지면·차분·뉴스 테마는 형광펜 밑줄), `**굵게**` 는 굵게, `\n` 은 줄바꿈. 모든 장에 `source`(아래 출처 줄)·`alt`(대체 텍스트)·`seconds`(릴스에서 머무는 시간)를 달 수 있다.

## 장 종류

| type | 필드 | 쓰는 곳 |
|---|---|---|
| cover | kicker?, title, sub?, big{value, unit}?, image?, image_mode `bg`(사진 위에 글) · `top`(사진 아래 글) | 첫 장: 왜 읽어야 하는지 |
| point | no, kicker?, title, body?, image? | 핵심 하나 (큰 번호 01·02…) |
| list | kicker?, title, items[문자열 또는 {text, sub}] | 나열 |
| steps | kicker?, title, items[…] | 순서 (마지막 단계 강조) |
| checks | kicker?, title, items[{text, ok}] | 할 것 ✓ / 피할 것 ✕ |
| compare | kicker?, title, left{label, items}, right{label, items} | 나쁜 예(왼쪽) vs 좋은 예(오른쪽) |
| stat | kicker?, value, unit?, label, note? | 숫자 하나 크게 (출처 필수) |
| quote | text, who? | 인용 |
| image | image, caption | 사진 한 장 + 한 줄 |
| summary | title, items[…] | 한눈에 정리 (번호 상자) |
| cta | title?, sub?, actions[`save`·`share`·`follow`]? | 마지막 장: 저장·공유·팔로우 |

## 크기
- `4:5` 1080×1350: 인스타 피드 기본(세로로 가장 크게 보인다)
- `1:1` 1080×1080: 정사각 피드, 링크드인 문서
- `9:16` 1080×1920: 스토리·릴스 (`--reels` 영상도 이 크기)

## 결과
`out/4x5/01.png …`, `out/cards-4x5.pdf`(링크드인 문서 게시물로 올릴 수 있다), `out/contact.jpg`(휴대폰 크기 미리보기), `out/caption.txt`(캡션 + 해시태그 + 대체 텍스트), `out/reels.mp4`.
`out/_cards-*.html` 은 렌더에 쓴 페이지. 브라우저로 열어 바로 볼 수 있다.
