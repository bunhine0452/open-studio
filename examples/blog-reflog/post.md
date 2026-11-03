---
{
  "title": "reset --hard로 날린 커밋, git reflog로 되살리기",
  "title_options": ["git reset --hard 되돌리기: reflog로 커밋 살리기", "날린 커밋 살리는 git reflog 사용법 (30일 안에)", "git reset --hard 실수했을 때 바로 할 일 3가지"],
  "description": "git reset --hard로 커밋을 날렸어도 reflog에 기록이 남아 있으면 되살릴 수 있어요. 명령 세 줄과 못 살리는 경우, 보관 기간 설정까지 정리했어요.",
  "keyword": "git reflog",
  "tags": ["git", "git reflog", "reset --hard", "개발 팁", "깃"],
  "thumbnail": {"title": "날린 커밋,\n[reflog]로 살리기", "sub": "명령 세 줄 · 못 살리는 경우까지", "theme": "paper"},
  "sources": [
    {"title": "git 공식 문서 · git-reflog", "url": "https://git-scm.com/docs/git-reflog"},
    {"title": "git 공식 문서 · git-config (gc.reflogExpire)", "url": "https://git-scm.com/docs/git-config"}
  ]
}
---
`git reset --hard`를 잘못 쳐서 커밋이 사라졌다면, 아직 늦지 않았어요. git은 HEAD가 움직일 때마다 그 자리를 **reflog**라는 기록에 따로 적어 둡니다. 이 기록에서 사라진 커밋 번호를 찾아 다시 가면 돼요.

## git reflog가 하는 일

평소에 보는 `git log`는 지금 브랜치에서 이어지는 커밋만 보여 줍니다. 그래서 reset으로 두 칸 뒤로 가면, 그 위에 있던 커밋은 log에서 안 보여요. 지워진 것처럼 보이지만 저장소 안에는 아직 남아 있습니다.

`git reflog`는 다릅니다. HEAD가 거쳐 간 자리를 시간 순서대로 모두 보여 줘요. 커밋, 체크아웃, reset, rebase처럼 HEAD를 옮긴 일이 한 줄씩 쌓입니다.

## 날린 커밋 되살리기 (명령 세 줄)

**1단계.** 기록을 봅니다.

```
git reflog
```

**2단계.** reset 하기 직전 줄을 찾습니다. `HEAD@{1}: commit: …`처럼 생긴 줄이에요. 앞의 일곱 글자가 커밋 번호입니다.

**3단계.** 그 자리로 다시 갑니다.

```
git reset --hard HEAD@{1}
```

번호를 직접 써도 됩니다(`git reset --hard 53c9e32`). 이제 `git log`를 보면 사라졌던 커밋이 그대로 돌아와 있어요.

> 지금 작업을 건드리지 않고 살리고 싶다면 새 브랜치로 꺼내 두세요: `git branch rescue HEAD@{1}`

## 언제까지 살릴 수 있나

reflog 기록은 영원히 남지 않습니다. git 설정의 기본값은 이렇습니다.

| 설정 | 기본값 | 뜻 |
|---|---|---|
| gc.reflogExpire | 90일 | 지금 브랜치에서 닿는 커밋의 기록 |
| gc.reflogExpireUnreachable | 30일 | 어디서도 닿지 않는 커밋(날린 커밋)의 기록 |

날린 커밋은 보통 30일 안에 살려야 해요. 그 뒤 `git gc`가 돌면 정리될 수 있습니다. 기간을 늘리려면 `git config gc.reflogExpireUnreachable "90 days"`처럼 바꿀 수 있어요.

## reflog로도 못 살리는 경우

- **한 번도 커밋하지 않은 변경**: reflog는 커밋만 기억합니다. 저장만 하고 커밋하지 않은 수정은 `reset --hard` 뒤에 남지 않아요.
- **다른 컴퓨터에서 한 작업**: reflog는 내 저장소에만 있는 기록이라, 원격 저장소나 동료 컴퓨터의 기록은 보이지 않습니다.
- **오래전에 정리된 기록**: 위의 보관 기간이 지나 정리됐다면 찾기 어렵습니다.

그래서 `reset --hard` 앞에는 습관처럼 커밋부터 해 두는 편이 안전해요. 지울 생각이었더라도 커밋 하나는 30일 동안 보험이 됩니다.

## 자주 묻는 질문

**브랜치를 통째로 지웠어요.** 지운 브랜치의 마지막 커밋도 reflog에 남아 있어요. `git reflog`에서 그 커밋을 찾아 `git branch 이름 커밋번호`로 다시 만들면 됩니다.

**rebase를 잘못했어요.** 마찬가지로 reflog에서 rebase 시작 직전 줄(`rebase (start)` 바로 아래)을 찾아 그 자리로 reset하면 돼요.

**push까지 해 버렸어요.** 원격을 고쳐야 하니 혼자 쓰는 브랜치인지 먼저 확인하세요. 여럿이 쓰는 브랜치라면 reset 대신 `git revert`로 되돌리는 편이 안전합니다.

## 오늘 해 볼 것

아무 저장소에서나 `git reflog`를 한 번 쳐 보세요. 내가 지난 며칠 동안 HEAD를 어디로 옮겼는지 한눈에 보입니다. 실수했을 때 어디를 봐야 하는지 알아 두는 것만으로 반은 끝난 거예요.
