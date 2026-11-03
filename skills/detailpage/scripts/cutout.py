# /// script
# requires-python = ">=3.10,<3.13"
# dependencies = ["rembg[cpu]>=2.0.60", "pillow"]
# ///
"""누끼(배경 제거): 상품 사진 → 투명 PNG. 오픈소스 rembg(MIT) + U²-Net 모델, 내 컴퓨터에서 돈다.
처음 한 번 모델(약 170MB)을 내려받는다.

uv run cutout.py <사진> <결과.png> [--model isnet-general-use]
"""
import sys
from pathlib import Path

from PIL import Image
from rembg import new_session, remove

if len(sys.argv) < 3:
    sys.exit(__doc__)
model = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else "isnet-general-use"
src, dst = Path(sys.argv[1]), Path(sys.argv[2])
out = remove(Image.open(src).convert("RGB"), session=new_session(model), alpha_matting=False, post_process_mask=True)
out = out.crop(out.getbbox())
out.save(dst)
print(dst, out.size)
