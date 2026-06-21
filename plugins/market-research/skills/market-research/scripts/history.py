#!/usr/bin/env python3
"""Non-repeat memory for market-research suggestions.

history.json holds every candidate ever suggested so a run can avoid repeating
itself. Identity key = package if present, else the lowercased/stripped name.

Subcommands (candidates read as a JSON array on stdin):
  filter --history H.json   -> print the candidates minus already-seen ones
  add    --history H.json   -> append candidates to H.json, print {added,total}

Date/run_id for added entries come from --date / --run-id (the skill passes the
run date); both default to empty strings so the script is deterministic and
needs no clock. Stdlib-only, no pip.
"""
import sys, json, argparse, os

def cand_key(entry):
    """Canonical identity for a candidate. Package wins; else lowercased name."""
    pkg = entry.get("package")
    if pkg:
        return str(pkg).strip()
    return str(entry.get("name", "")).strip().lower()

def load_history(path):
    if not os.path.exists(path):
        return {"suggestions": []}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data.setdefault("suggestions", [])
    return data

def seen_keys(history):
    return {s.get("key") for s in history["suggestions"]}

def read_candidates():
    data = json.load(sys.stdin)
    if not isinstance(data, list):
        raise ValueError("candidates stdin must be a JSON array")
    return data

def cmd_filter(args):
    history = load_history(args.history)
    seen = seen_keys(history)
    cands = read_candidates()
    survivors = [c for c in cands if cand_key(c) not in seen]
    print(json.dumps(survivors, indent=2))

def cmd_add(args):
    history = load_history(args.history)
    seen = seen_keys(history)
    cands = read_candidates()
    added = 0
    for c in cands:
        k = cand_key(c)
        if k in seen:
            continue
        history["suggestions"].append({
            "key": k,
            "name": c.get("name"),
            "package": c.get("package"),
            "date": args.date,
            "run_id": args.run_id,
        })
        seen.add(k)
        added += 1
    os.makedirs(os.path.dirname(os.path.abspath(args.history)), exist_ok=True)
    with open(args.history, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)
    print(json.dumps({"added": added, "total": len(history["suggestions"])}, indent=2))

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("filter", "add"):
        p = sub.add_parser(name)
        p.add_argument("--history", required=True)
        p.add_argument("--date", default="")
        p.add_argument("--run-id", default="")
    args = ap.parse_args()
    {"filter": cmd_filter, "add": cmd_add}[args.cmd](args)

if __name__ == "__main__":
    main()
