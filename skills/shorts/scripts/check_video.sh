#!/usr/bin/env bash
# 완성 영상 검수: 규격 · 전체 디코딩 · 통합 음량(-16 LUFS 근처) · 컨택트시트(16장)
# bash check_video.sh <영상.mp4>
set -euo pipefail
f="$1"
dir="$(dirname "$f")"
ffprobe -v error -show_entries format=duration,size:stream=codec_name,width,height,r_frame_rate,sample_rate -of compact "$f"
ffmpeg -v error -i "$f" -f null - && echo "decode: OK"
ffmpeg -hide_banner -i "$f" -af ebur128=framelog=quiet -f null - 2>&1 | grep -A1 "Integrated loudness" | tail -1
dur=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$f")
step=$(python3 -c "print(max(0.5, $dur / 16))")
ffmpeg -v error -y -i "$f" -vf "fps=1/$step,scale=270:-1,tile=8x2" -frames:v 1 "$dir/_contact.jpg"
echo "contact sheet: $dir/_contact.jpg (확인 후 지우기)"
