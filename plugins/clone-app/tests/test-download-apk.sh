#!/usr/bin/env bash
set -uo pipefail
SCRIPT="$(dirname "$0")/../skills/clone-app/scripts/download-apk.sh"
fail=0
check() { [[ "$2" == "$3" ]] && echo "PASS: $1" || { echo "FAIL: $1 — expected '$2' got '$3'"; fail=1; }; }

tmp="$(mktemp -d)"

# Stub curl: writes a minimal zip containing manifest.json + two apk entries → xapk
cat > "$tmp/fakecurl-xapk.sh" <<'EOF'
#!/usr/bin/env bash
out=""; prev=""
for a in "$@"; do [[ "$prev" == "--output" ]] && out="$a"; prev="$a"; done
workdir="$(mktemp -d)"
echo '{}' > "$workdir/manifest.json"
echo 'a' > "$workdir/base.apk"; echo 'b' > "$workdir/config.apk"
( cd "$workdir" && zip -q -r "$out" . )
exit 0
EOF
chmod +x "$tmp/fakecurl-xapk.sh"

path="$(CLONE_APP_CURL="$tmp/fakecurl-xapk.sh" bash "$SCRIPT" com.example.app "$tmp/out" 2>/dev/null)"; rc=$?
check "xapk exit 0" "0" "$rc"
check "xapk extension" "xapk" "${path##*.}"

# Stub curl that always fails → exit 1 after retries
cat > "$tmp/fakecurl-fail.sh" <<'EOF'
#!/usr/bin/env bash
exit 22
EOF
chmod +x "$tmp/fakecurl-fail.sh"
out2="$(CLONE_APP_CURL="$tmp/fakecurl-fail.sh" bash "$SCRIPT" com.example.app "$tmp/out2" 2>/dev/null)"; rc2=$?
check "fail exit 1" "1" "$rc2"

rm -rf "$tmp"
exit $fail
