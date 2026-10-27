#!/usr/bin/env python3
"""Which text each label shows in a given language — from the decoded Unity
Localization data (StringTable + SharedTableData + LocalizeStringEvent). Stdlib only.

    python3 ui-localize.py <game-assets> --locale tr > texts-tr.json

Output: {"locale": "tr", "texts": {<text component id>: "<string>"}, "unresolved": n}.
A canvas dump carries the text a label was saved with (often English or a
placeholder); the game swaps it at runtime through a LocalizeStringEvent whose
update call targets the label. Strings with {0} placeholders are filled by code
and stay as they are.
"""
import argparse
import glob
import json
import os
import sys


def rows(root, suffix):
    for p in glob.glob(os.path.join(root, "scripts", "*", "*" + suffix)):
        with open(p) as f:
            for line in f:
                yield json.loads(line)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--locale", required=True, help="locale code, e.g. tr, en, de")
    a = ap.parse_args(argv)

    shared_guid = {}                     # SharedTableData id -> collection guid
    name_guid, key_ids = {}, {}          # collection name -> guid; guid -> {key name: id}
    for r in rows(a.root, ".Tables.SharedTableData.jsonl"):
        f = r["fields"]
        g = (f.get("m_TableCollectionNameGuidString") or "").replace("-", "")
        shared_guid[r["id"]] = g
        name_guid[f.get("m_TableCollectionName") or ""] = g
        key_ids[g] = {e.get("m_Key"): int(e["m_Id"]) for e in f.get("m_Entries") or []}
    by_guid, any_table = {}, {}
    for r in rows(a.root, ".Tables.StringTable.jsonl"):
        f = r["fields"]
        if ((f.get("m_LocaleId") or {}).get("m_Code") or "") != a.locale:
            continue
        entries = {int(e["m_Id"]): e.get("m_Localized") for e in f.get("m_TableData") or []}
        g = shared_guid.get(((f.get("m_SharedData") or {}).get("ref")) or "", "")
        by_guid.setdefault(g, {}).update(entries)
        any_table.update(entries)
    if not any_table:
        print(f"ERROR: no StringTable for locale {a.locale!r}", file=sys.stderr)
        return 1

    texts, unresolved = {}, 0
    for r in rows(a.root, ".Components.LocalizeStringEvent.jsonl"):
        f = r["fields"]
        ref = f.get("m_StringReference") or {}
        table_ref = (ref.get("m_TableReference") or {}).get("m_TableCollectionName") or ""
        # a table is referenced by "GUID:<guid>" or by its collection name
        guid = table_ref[5:].replace("-", "") if table_ref.startswith("GUID:") else name_guid.get(table_ref, "")
        entry = ref.get("m_TableEntryReference") or {}
        key = entry.get("m_KeyId")
        if not key and entry.get("m_Key"):          # referenced by key name, id left 0
            key = (key_ids.get(guid) or {}).get(entry["m_Key"])
        table = by_guid.get(guid) or any_table
        s = table.get(int(key)) if key is not None else None
        targets = [c["m_Target"]["ref"] for c in
                   ((f.get("m_UpdateString") or {}).get("m_PersistentCalls") or {}).get("m_Calls") or []
                   if (c.get("m_Target") or {}).get("ref") and
                   c.get("m_MethodName") in ("SetText", "set_text", "set_Text", "SetTextWithoutNotify")]
        if s is None or not targets:
            unresolved += 1
            continue
        for t in targets:
            texts[t] = s
    json.dump({"locale": a.locale, "texts": texts, "unresolved": unresolved}, sys.stdout,
              ensure_ascii=False, indent=1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
