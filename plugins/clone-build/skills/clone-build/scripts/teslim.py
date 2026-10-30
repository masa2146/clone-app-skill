#!/usr/bin/env python3
"""Deliver a task's evidence to the dated delivery folder. Stdlib only.

    teslim.py <ID> <short-name> <file>... [--not "one line"] [--project DIR]

Copies the files to <teslim_dir>/<YYYY-MM-DD>/<HHMM>_<ID>_<short-name>/ as
NN_<ascii name>, writes README.md there, puts the entry on top of TESLIMLER.md,
fills the task file's "## Teslim" section and marks the task teslimde. iz.json in
the folder fingerprints the files the branch changed, so `tasks.py bayat` can tell
when the evidence no longer shows the code. Prints
every full path in a code block, one per line, ready to paste into an editor.
"""
import argparse
import datetime
import json
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tasks  # noqa: E402


def ascii_name(name):
    stem, ext = os.path.splitext(os.path.basename(name))
    return tasks.slug(stem, 60) + ext.lower()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("id")
    ap.add_argument("name")
    ap.add_argument("files", nargs="+")
    ap.add_argument("--not", dest="note", default="")
    ap.add_argument("--project", default=".")
    a = ap.parse_args(argv)

    with open(os.path.join(a.project, "Docs", "project.json")) as f:
        teslim_dir = json.load(f)["teslim_dir"]
    missing = [p for p in a.files if not os.path.exists(p)]
    if missing:
        sys.exit("ERROR: missing: " + ", ".join(missing))
    lines, ts = tasks.load(a.project)
    t = tasks.find(ts, a.id)

    now = datetime.datetime.now()
    out = os.path.join(teslim_dir, now.strftime("%Y-%m-%d"), f"{now:%H%M}_{t['id']}_{tasks.slug(a.name)}")
    os.makedirs(out, exist_ok=True)
    copied = []
    for i, src in enumerate(a.files, 1):
        dst = os.path.join(out, f"{i:02d}_{ascii_name(src)}")
        (shutil.copytree if os.path.isdir(src) else shutil.copy2)(src, dst)
        copied.append(dst)
    with open(os.path.join(out, "iz.json"), "w") as f:
        json.dump(tasks.fingerprint(a.project, tasks.touched_files(a.project)), f, ensure_ascii=False, indent=1)
    readme = os.path.join(out, "README.md")
    with open(readme, "w") as f:
        f.write(f"# {t['id']} — {t['is']}\n\n{now:%Y-%m-%d %H:%M}\n\n" + (a.note + "\n\n" if a.note else "")
                + "\n".join(f"- `{p}`" for p in copied) + "\n")

    index = os.path.join(teslim_dir, "TESLIMLER.md")
    head, body = "# Teslimler\n\nEn yeni üstte.\n\n", ""
    if os.path.exists(index):
        with open(index) as f:
            text = f.read()
        cut = text.find("\n- ")
        head, body = (text, "") if cut < 0 else (text[:cut + 1], text[cut + 1:])
    entry = f"- {now:%Y-%m-%d %H:%M} · {t['id']} {t['is']}" + (f" — {a.note}" if a.note else "") + f" · `{out}`\n"
    with open(index, "w") as f:
        f.write(head + entry + body)

    if t["ayrinti"]:
        p = os.path.join(a.project, t["ayrinti"])
        if os.path.exists(p):
            with open(p) as f:
                s = f.read()
            block = f"\n{now:%Y-%m-%d %H:%M}" + (f" — {a.note}" if a.note else "") + "\n```\n" + "\n".join(copied) + "\n```\n"
            mark = "## Teslim\n"
            i = s.find(mark)
            s = s[:i + len(mark)] + block + s[i + len(mark):] if i >= 0 else s + "\n" + mark + block
            s = (re.sub(r"^teslim: .*$", f"teslim: {out}", s, count=1, flags=re.M) if re.search(r"^teslim: ", s, re.M)
                 else s.replace("\n---\n", f"\nteslim: {out}\n---\n", 1))
            with open(p, "w") as f:
                f.write(s)
    tasks.set_status(a.project, lines, ts, t, "teslimde")

    print(f"Teslim: {t['id']} — {t['is']}\n```\n" + "\n".join(copied + [readme]) + "\n```")
    return 0


if __name__ == "__main__":
    sys.exit(main())
