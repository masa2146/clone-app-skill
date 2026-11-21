#!/bin/bash
# gem.sh — drive Gemini image (Nano Banana Pro) and video generation through the gstack browser ($B).
#   gem.sh gen   <prompt.txt> <aspect> <out.png> [ref.png...]   new chat, image tool, Pro model, aspect, paste refs, send, download full size
#   gem.sh again <prompt.txt> <out.png>                          same chat, edit the last image ("change only X")
#   gem.sh dl    <out.png>                                       download the last image of the open chat
#   gem.sh vid   <prompt.txt> <aspect> <out.mp4> [ref.png...]   video tool
# Env: GEM_BROWSE_ROOT (required) = a repo whose gstack browser profile is signed in to Gemini — the $B daemon is picked by
#      git root, so calling from a worktree opens a NEW signed-out browser. GEM_TAB = tab id when the browser is shared.
#      GEM_B overrides the browse command. Paths must be ABSOLUTE (the script cd's).
# Never upload the source game's art. Aspect labels: "1:1", "16:9", "9:16", "4:3", "3:4" (UI may be Turkish or English).
B="${GEM_B:-$HOME/.claude/skills/gstack/browse/dist/browse --headed}"
cd "${GEM_BROWSE_ROOT:?set GEM_BROWSE_ROOT to the repo whose gstack browser is signed in to Gemini}" || exit 1
[ -n "$GEM_TAB" ] && { $B tab "$GEM_TAB" >/dev/null || exit 1; }
PY=$(for p in python3 /Library/Frameworks/Python.framework/Versions/3.11/bin/python3; do $p -c 'import PIL' 2>/dev/null && { echo $p; break; }; done)  # Pillow'lu python
A=$(getconf DARWIN_USER_TEMP_DIR)  # Playwright indirmeleri buraya dusurur
DL='"(Tam boyutlu resmi indir|Download full size image)'
ref() { for k in 1 2 3 4 5 6 7 8 9 10; do r=$($B snapshot -i 2>/dev/null | grep -v cursor: | grep -E "$1" | head -1 | grep -o '@e[0-9]*'); [ -n "$r" ] && { echo $r; return; }; sleep 2; done; echo "REF_MISSING $1" >&2; }
newchat() {
  $B goto https://gemini.google.com/app >/dev/null; sleep 3
  for t in 1 2 3; do
    $B click "$(ref '\[button\] "(Yükleme ve araçlar|Upload & tools|Tools)')" >/dev/null; sleep 1
    $B click "$(ref '"(Görüntü oluştur|Create image)')" >/dev/null; sleep 2
    $B snapshot -i 2>/dev/null | grep -qE '(Resimler öğesinin seçimini kaldır|Deselect Image|Deselect Create image)' && break; $B press Escape >/dev/null
  done
  m=$(ref '(Mod seçiciyi aç|Open mode picker)')
  $B snapshot -i 2>/dev/null | grep -qE '(şu anda Pro modunda|currently Pro)' || { $B click "$m" >/dev/null; sleep 1; $B click "$(ref '"3(\.[0-9])? Pro')" >/dev/null; sleep 1; }
  $B click "$(ref '"(En-boy oranı|Aspect ratio)')" >/dev/null; sleep 1; $B click "$(ref "\[menuitemradio\] \"$1\"")" >/dev/null; sleep 1
}
upload() { for f in "$@"; do osascript -e "set the clipboard to (read (POSIX file \"$f\") as «class PNGf»)"; $B click "$(ref '\[textbox\]')" >/dev/null; $B press Meta+v >/dev/null; sleep 8; done; }
send() {
  $B fill "$(ref '\[textbox\]')" "$(cat "$1")" >/dev/null; sleep 1
  s=$($B snapshot -i 2>/dev/null); n0=$(grep -cE "$DL" <<<"$s"); k0=$(grep -cE '"(Kopyala|Copy)"' <<<"$s"); again=1
  $B click "$(ref '"(Mesaj gönder|Send message)"')" >/dev/null
  for i in $(seq 1 240); do sleep 5; s=$($B snapshot -i 2>/dev/null); n=$(grep -cE "$DL" <<<"$s"); [ "$n" -gt "$n0" ] && return 0
    # a request Gemini dropped returns to the new-chat page (no "Change style", URL loses the chat id)
    [ "$i" -gt 6 ] && { grep -qE '"(Stilini değiştir|Change style)"' <<<"$s" || $B url 2>/dev/null | grep -qE '/app/?$'; } && { echo "dropped by Gemini" >&2; return 1; }
    [ "$again" = 1 ] && [ "$(grep -cE '"(Kopyala|Copy)"' <<<"$s")" -gt "$k0" ] && { again=0; $B fill "$(ref '\[textbox\]')" "Use the image generation tool and create this image now, exactly as described in my previous message." >/dev/null; sleep 1; $B click "$(ref '"(Mesaj gönder|Send message)"')" >/dev/null; }
  done; return 1
}
download() {
  M=$HOME/.gem_mark; touch $M
  r=$($B snapshot -i 2>/dev/null | grep -v cursor: | grep -E "$DL" | tail -1 | grep -o '@e[0-9]*')
  $B click "$r" >/dev/null
  for i in $(seq 1 30); do sleep 2; f=$(find $A -maxdepth 2 -path '*playwright-artifacts*' -type f -newer $M -size +100k ! -name '*.crdownload' 2>/dev/null | head -1); [ -n "$f" ] && { sleep 2; $PY -c "from PIL import Image; im=Image.open('$f'); im.convert('RGB').save('$1'); print('saved',im.size)"; return 0; }; done; echo "download failed"; return 1
}
# Video tool: an intro screen ("Try") appears the first time; aspect "Portrait (9:16)" or "Landscape (16:9)".
# Bitince ekranda video indirme düğmesi belirir; indirilen dosya olduğu gibi (mp4) kopyalanır.
VDL='"(Videoyu indir|Download video|İndir|Download)"'
newvid() {
  $B goto https://gemini.google.com/app >/dev/null; sleep 3
  $B click "$(ref '\[button\] "(Yükleme ve araçlar|Upload & tools|Tools)')" >/dev/null; sleep 1
  $B click "$(ref '"(Video oluştur|Create video)')" >/dev/null; sleep 2
  r=$($B snapshot -i 2>/dev/null | grep -v cursor: | grep -E '\[button\] "(Dene|Try)"' | head -1 | grep -o '@e[0-9]*'); [ -n "$r" ] && { $B click "$r" >/dev/null; sleep 2; }
  $B click "$(ref '"(En boy oranı|Aspect ratio)')" >/dev/null; sleep 1; $B click "$(ref "\[menuitemradio\] \"$1")" >/dev/null; sleep 1
}
sendvid() {
  $B fill "$(ref '\[textbox\]')" "$(cat "$1")" >/dev/null; sleep 1
  s=$($B snapshot -i 2>/dev/null); n0=$(grep -cE "$VDL" <<<"$s"); k0=$(grep -cE '"(Kopyala|Copy)"' <<<"$s")
  $B click "$(ref '"(Mesaj gönder|Send message)"')" >/dev/null
  for i in $(seq 1 180); do sleep 5; s=$($B snapshot -i 2>/dev/null); n=$(grep -cE "$VDL" <<<"$s"); [ "$n" -gt "$n0" ] && return 0
    # video yerine yalnız yazı geldiyse ("I'm having a hard time…") reddetmiştir: beklemeden dön
    t=$($B snapshot 2>/dev/null | grep -A1 'Gemini şunu dedi' | tail -1)
    grep -qiE "hard time|can.t help|unable to|went wrong|zorlan|yardımcı olamam|oluşturamıyorum|bir sorun" <<<"$t" && { echo "refused by Gemini: ${t:0:160}" >&2; return 1; }
    [ "$i" -gt 6 ] && $B url 2>/dev/null | grep -qE '/app/?$' && { echo "dropped by Gemini" >&2; return 1; }; done; return 1
}
dlvid() {
  M=$HOME/.gem_mark; touch $M
  $B click "$($B snapshot -i 2>/dev/null | grep -v cursor: | grep -E "$VDL" | tail -1 | grep -o '@e[0-9]*')" >/dev/null
  for i in $(seq 1 60); do sleep 2; f=$(find $A -maxdepth 2 -path '*playwright-artifacts*' -type f -newer $M -size +100k ! -name '*.crdownload' 2>/dev/null | head -1); [ -n "$f" ] && { sleep 3; cp "$f" "$1"; echo "saved $(du -k "$1" | cut -f1)k"; return 0; }; done; echo "download failed"; return 1
}
cmd=$1; shift
case $cmd in
  vid) pf=$1; asp=$2; out=$3; shift 3; newvid "$asp"; [ $# -gt 0 ] && upload "$@"; sendvid "$pf" && dlvid "$out" ;;
  gen) pf=$1; asp=$2; out=$3; shift 3; newchat "$asp"; [ $# -gt 0 ] && upload "$@"; send "$pf" && download "$out" ;;
  again) pf=$1; out=$2; send "$pf" && download "$out" ;;
  dl) download "$1" ;;
esac
