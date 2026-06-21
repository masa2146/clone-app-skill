#!/usr/bin/env bash
set -uo pipefail
SCRIPT="$(dirname "$0")/../skills/clone-app/scripts/download-apk.sh"
fail=0
check() { [[ "$2" == "$3" ]] && echo "PASS: $1" || { echo "FAIL: $1 — expected '$2' got '$3'"; fail=1; }; }

tmp="$(mktemp -d)"

# Find the --output target in a curl arg list, and the request URL (http... arg).
# Shared helper sourced by the stubs below.
cat > "$tmp/argparse.sh" <<'EOF'
out=""; url=""; prev=""
for a in "$@"; do
  [[ "$prev" == "--output" || "$prev" == "-o" ]] && out="$a"
  [[ "$a" == http*://* ]] && url="$a"
  prev="$a"
done
EOF

# Stub curl modelling the real two-step APKCombo flow:
#  call 1 (URL contains /download/apk) -> emit HTML page with an /r2?u= link
#  call 2 (URL contains /r2?u=)        -> emit a zip (manifest.json + 2 apk) => xapk
cat > "$tmp/fakecurl-xapk.sh" <<EOF
#!/usr/bin/env bash
source "$tmp/argparse.sh"
if [[ "\$url" == *"/download/apk"* ]]; then
  printf '%s' '<a href="/r2?u=https%3A%2F%2Fexample%2Ftest.xapk">Download</a>' > "\$out"
  exit 0
elif [[ "\$url" == *"/r2?u="* ]]; then
  workdir="\$(mktemp -d)"
  echo '{}' > "\$workdir/manifest.json"
  echo 'a' > "\$workdir/base.apk"; echo 'b' > "\$workdir/config.apk"
  ( cd "\$workdir" && zip -q -r "\$out" . )
  exit 0
fi
exit 1
EOF
chmod +x "$tmp/fakecurl-xapk.sh"

path="$(CLONE_APP_CURL="$tmp/fakecurl-xapk.sh" bash "$SCRIPT" com.example.app "$tmp/out" 2>/dev/null)"; rc=$?
check "xapk exit 0" "0" "$rc"
check "xapk extension" "xapk" "${path##*.}"

# Stub where the download page loads but contains NO /r2 link -> exit 1
cat > "$tmp/fakecurl-nolink.sh" <<EOF
#!/usr/bin/env bash
source "$tmp/argparse.sh"
if [[ "\$url" == *"/download/apk"* ]]; then
  printf '%s' '<html>no link here</html>' > "\$out"; exit 0
fi
exit 1
EOF
chmod +x "$tmp/fakecurl-nolink.sh"
out2="$(CLONE_APP_CURL="$tmp/fakecurl-nolink.sh" bash "$SCRIPT" com.example.app "$tmp/out2" 2>/dev/null)"; rc2=$?
check "no-link exit 1" "1" "$rc2"

# Stub curl that always fails -> exit 1 after retries
cat > "$tmp/fakecurl-fail.sh" <<'EOF'
#!/usr/bin/env bash
exit 22
EOF
chmod +x "$tmp/fakecurl-fail.sh"
out3="$(CLONE_APP_CURL="$tmp/fakecurl-fail.sh" bash "$SCRIPT" com.example.app "$tmp/out3" 2>/dev/null)"; rc3=$?
check "fail exit 1" "1" "$rc3"

rm -rf "$tmp"
exit $fail
