# /// script
# requires-python = ">=3.10"
# dependencies = ["playwright"]
# ///
"""설치 점검: 쇼츠를 만들기 전에 필요한 것이 다 있는지 보고, 없으면 설치 명령을 알려 준다.

uv run doctor.py
"""
from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path

OS = platform.system()
FIX = {
    "ffmpeg": {"Darwin": "brew install ffmpeg", "Linux": "sudo apt install ffmpeg", "Windows": "winget install Gyan.FFmpeg"},
    "chrome": {"Darwin": "https://www.google.com/chrome/ 에서 설치하거나: uvx playwright install chromium",
               "Linux": "uvx playwright install --with-deps chromium", "Windows": "uvx playwright install chromium"},
}


def ok(name, good, hint=""):
    print(f"{'✅' if good else '❌'} {name}" + ("" if good else f"\n   → {hint}"))
    return good


def main():
    print(f"운영체제: {OS} {platform.machine()}\n")
    results = [ok("uv", shutil.which("uv") is not None, "https://docs.astral.sh/uv/ 설치 안내를 따르세요")]
    results.append(ok("ffmpeg", shutil.which("ffmpeg") is not None, FIX["ffmpeg"].get(OS, "ffmpeg 를 설치하세요")))
    fonts = Path(__file__).resolve().parents[1] / "fonts"
    results.append(ok("글꼴 (Pretendard)", (fonts / "Pretendard-Black.otf").exists(), "스킬 폴더를 통째로 다시 복사하세요"))
    chrome = False
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            for kw in ({"channel": "chrome"}, {}):
                try:
                    p.chromium.launch(**kw).close()
                    chrome = True
                    break
                except Exception:
                    continue
    except Exception:
        pass
    results.append(ok("Chrome (모션 렌더)", chrome, FIX["chrome"].get(OS, "") + "\n   (없어도 render.py --simple 로는 만들 수 있어요)"))
    net = subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "anullsrc", "-t", "0.1", "-f", "null", "-"],
                         capture_output=True).returncode == 0 if shutil.which("ffmpeg") else False
    results.append(ok("ffmpeg 동작", net, "ffmpeg 를 다시 설치하세요"))
    print("\n준비 완료! Claude Code 에서 \"쇼츠 만들어 줘: <주제>\" 라고 말해 보세요." if all(results)
          else "\n❌ 표시를 먼저 고치고 다시 실행하세요.")


if __name__ == "__main__":
    main()
