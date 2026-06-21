#!/usr/bin/env bash
set -uo pipefail
SCRIPT="$(dirname "$0")/../skills/clone-app/scripts/download-apk.sh"
fail=0
check() { [[ "$2" == "$3" ]] && echo "PASS: $1" || { echo "FAIL: $1 — expected '$2' got '$3'"; fail=1; }; }

tmp="$(mktemp -d)"

# Stub apkeep modelling the real CLI:
#   apkeep -a <package> -d <source> <out_dir>
# parse out the package and the out_dir (last arg), then drop an artifact there.
# CLONE_APP_FAKE_EXT picks which extension the stub produces; "fail" makes it
# exit non-zero without writing anything.
cat > "$tmp/fakeapkeep.sh" <<'EOF'
#!/usr/bin/env bash
pkg=""; outdir=""; prev=""
for a in "$@"; do
  [[ "$prev" == "-a" || "$prev" == "--app" ]] && pkg="$a"
  outdir="$a"   # last positional wins; apkeep takes OUTPATH last
  prev="$a"
done
case "$CLONE_APP_FAKE_EXT" in
  fail) exit 1 ;;
  xapk)
    workdir="$(mktemp -d)"
    echo '{}' > "$workdir/manifest.json"
    echo 'a' > "$workdir/base.apk"; echo 'b' > "$workdir/config.apk"
    ( cd "$workdir" && zip -q -r "$outdir/$pkg.xapk" . ) ;;
  *) echo 'apk-bytes' > "$outdir/$pkg.apk" ;;
esac
exit 0
EOF
chmod +x "$tmp/fakeapkeep.sh"

# XAPK case
path="$(CLONE_APP_APKEEP="$tmp/fakeapkeep.sh" CLONE_APP_FAKE_EXT=xapk \
  bash "$SCRIPT" com.example.app "$tmp/out" 2>/dev/null)"; rc=$?
check "xapk exit 0" "0" "$rc"
check "xapk extension" "xapk" "${path##*.}"
check "xapk renamed to app.*" "app.xapk" "$(basename "$path")"

# APK case
path2="$(CLONE_APP_APKEEP="$tmp/fakeapkeep.sh" CLONE_APP_FAKE_EXT=apk \
  bash "$SCRIPT" com.example.app "$tmp/out-apk" 2>/dev/null)"; rc2=$?
check "apk exit 0" "0" "$rc2"
check "apk extension" "apk" "${path2##*.}"

# apkeep failure -> exit 1
out3="$(CLONE_APP_APKEEP="$tmp/fakeapkeep.sh" CLONE_APP_FAKE_EXT=fail \
  bash "$SCRIPT" com.example.app "$tmp/out3" 2>/dev/null)"; rc3=$?
check "fail exit 1" "1" "$rc3"

# apkeep binary missing -> exit 1
out4="$(CLONE_APP_APKEEP="$tmp/does-not-exist-apkeep" \
  bash "$SCRIPT" com.example.app "$tmp/out4" 2>/dev/null)"; rc4=$?
check "missing-binary exit 1" "1" "$rc4"

rm -rf "$tmp"
exit $fail
