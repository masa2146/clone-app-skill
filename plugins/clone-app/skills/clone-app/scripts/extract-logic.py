#!/usr/bin/env python3
"""Surface in-app logic signals from a decompiled APK source tree.

Walks .java/.kt sources and flags ViewModel/use-case classes, input-validation
calls, state-machine enums/sealed classes, and Room @Entity/@Dao declarations.
Stdlib-only. Emits a JSON signals inventory on stdout (or --out FILE); the
Phase 8 fidelity subagent distills it (plus the sources) into logic-digest.md.
"""
import os, re, json, argparse

SRC_EXT = (".java", ".kt")
VALIDATION_PAT = re.compile(r'(Pattern\.compile|\.matches\(|isValid|require\(|Validators?\.)')

def _iter_sources(root):
    for dp, _, files in os.walk(root):
        for fn in files:
            if fn.endswith(SRC_EXT):
                yield os.path.join(dp, fn)

def extract(root):
    vms, ucs, vals, enums, entities, daos = [], [], [], [], [], []
    for path in _iter_sources(root):
        name = os.path.splitext(os.path.basename(path))[0]
        rel = os.path.relpath(path, root)
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if name.endswith("ViewModel"):
            vms.append({"file": rel, "name": name})
        if name.endswith(("UseCase", "Interactor")):
            ucs.append({"file": rel, "name": name})
        for i, line in enumerate(text.splitlines(), 1):
            if VALIDATION_PAT.search(line):
                vals.append({"file": rel, "line": i, "snippet": line.strip()[:160]})
        for m in re.finditer(r'\b(?:enum|sealed)\s+class\s+(\w+)', text):
            enums.append({"file": rel, "name": m.group(1)})
        for m in re.finditer(r'\benum\s+(\w+)\s*\{', text):
            enums.append({"file": rel, "name": m.group(1)})
        if re.search(r'@Entity\b', text):
            entities.append({"file": rel, "name": name})
        if re.search(r'@Dao\b', text):
            daos.append({"file": rel, "name": name})
    return {
        "root": root,
        "viewmodels": vms,
        "usecases": ucs,
        "validation": vals,
        "state_enums": enums,
        "room_entities": entities,
        "room_daos": daos,
    }

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root", help="decompile output root (sources)")
    ap.add_argument("--out")
    args = ap.parse_args()
    text = json.dumps(extract(args.root), indent=2)
    if args.out:
        with open(args.out, "w") as f:
            f.write(text)
    else:
        print(text)

if __name__ == "__main__":
    main()
