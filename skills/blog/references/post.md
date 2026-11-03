# post.md

맨 위 `---` 사이에 JSON 앞머리, 그 아래 마크다운 본문.

```markdown
---
{
  "title": "reset --hard로 날린 커밋, git reflog로 되살리기",
  "title_options": ["…", "…"],
  "description": "검색 결과 아래 회색 글로 보이는 요약 (50~160자)",
  "keyword": "git reflog",
  "tags": ["git", "개발 팁"],
  "thumbnail": {"title": "날린 커밋,\n[reflog]로 살리기", "sub": "명령 세 줄", "theme": "paper"},
  "sources": [{"title": "git 공식 문서", "url": "https://…", "file": "sources/01.txt"}]
}
---
첫 문단에 결론.

## 소제목
…
```
- `thumbnail.theme`: paper·neon·arcade·calm·news 또는 사용자 테마 `{"base", "colors"}`. `[강조]` 는 강조색.
- 표·코드 블록·인용(>)·목록 모두 붙여 넣기용 HTML 에 인라인 스타일로 들어간다. 번호 목록 사이에 코드 블록을 넣으면 번호가 다시 1부터 시작하니 "**1단계.**" 처럼 굵은 글로 쓴다.

## 점검 항목 (blog.py check)
| 항목 | 기준 |
|---|---|
| 표절 | 출처 원문과 공백 빼고 28자 이상 그대로 같으면 경고 (sources 의 file 이 있을 때) |
| 문체 | 번역투·상투구·줄표·꾸밈 부사·'X가 아니라 Y' (쇼츠 speakable 과 같은 규칙) |
| 광고 문구 | 최상급·100%·의약품 오인·추천·인증·다이어트 (상세페이지와 같은 규칙) |
| 키워드 | 본문에 없음 / 제목에 없음 / 300자에 한 번보다 많음 |
| 길이·구조 | 1,200자 미만·6,000자 초과, 소제목 3개 미만, 120자 넘는 문장, 대체 텍스트 없는 그림 |
| 출처 | sources 가 비어 있으면 경고 |
