#!/usr/bin/env bash
# Download a gameplay reference video at the best resolution the site serves.
#
#   fetch-reference-video.sh <url> <out.mp4> [section, e.g. "*00:01:10-00:02:30"]
#
# yt-dlp's default pick was 288x640 for one game while 720p and 1080x2400
# streams existed; screens measured from it were blurred guesses. Sorts by
# resolution and fps, asks the web_embedded client too, and warns under 720p.
set -uo pipefail
url=${1:?url} out=${2:?out.mp4}; section=${3:-}
command -v yt-dlp >/dev/null || { echo "ERROR: yt-dlp not installed (brew install yt-dlp)" >&2; exit 2; }
extra=(); [[ -n $section ]] && extra=(--download-sections "$section")
yt-dlp -q --no-playlist --extractor-args "youtube:player_client=default,web_embedded" \
  -S "res,fps,vcodec:h264" -f "bv*+ba/b" --merge-output-format mp4 ${extra[@]+"${extra[@]}"} -o "$out" "$url" || exit 1
if command -v ffprobe >/dev/null; then
  dim=$(ffprobe -v error -select_streams v:0 -show_entries stream=width,height -of csv=p=0:s=x "$out")
  echo "$out $dim"
  short=$(echo "$dim" | awk -Fx '{print ($1<$2)?$1:$2}')
  [[ ${short:-0} -lt 720 ]] && echo "WARNING: short side ${short}px < 720 — look for a better upload" >&2
fi
exit 0
