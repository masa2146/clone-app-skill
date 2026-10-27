#!/usr/bin/env python3
"""ui-localize.py: labels get the string of the requested language, whether the
event references its key by id or by name."""
import importlib.util
import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location(
    "ui_localize", os.path.join(HERE, "..", "skills", "clone-app", "scripts", "ui-localize.py"))
ul = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ul)
fails = []


def check(name, cond):
    print(f"{'PASS' if cond else 'FAIL'}: {name}")
    if not cond:
        fails.append(name)


def jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


with tempfile.TemporaryDirectory() as t:
    d = os.path.join(t, "scripts", "Unity.Localization")
    jsonl(os.path.join(d, "UnityEngine.Localization.Tables.SharedTableData.jsonl"), [
        {"id": "s:1", "fields": {"m_TableCollectionName": "UI", "m_TableCollectionNameGuidString": "ab-cd",
                                 "m_Entries": [{"m_Id": 7, "m_Key": "settings.title"}, {"m_Id": 8, "m_Key": "play"}]}}])
    jsonl(os.path.join(d, "UnityEngine.Localization.Tables.StringTable.jsonl"), [
        {"id": "t:1", "fields": {"m_LocaleId": {"m_Code": "tr"}, "m_SharedData": {"ref": "s:1"},
                                 "m_TableData": [{"m_Id": 7, "m_Localized": "Ayarlar"}, {"m_Id": 8, "m_Localized": "Oyna"}]}},
        {"id": "t:2", "fields": {"m_LocaleId": {"m_Code": "en"}, "m_SharedData": {"ref": "s:1"},
                                 "m_TableData": [{"m_Id": 7, "m_Localized": "Settings"}]}}])
    call = lambda target: {"m_PersistentCalls": {"m_Calls": [{"m_Target": {"ref": target}, "m_MethodName": "set_text"}]}}
    jsonl(os.path.join(d, "UnityEngine.Localization.Components.LocalizeStringEvent.jsonl"), [
        {"id": "e:1", "fields": {"m_StringReference": {"m_TableReference": {"m_TableCollectionName": "UI"},
                                                       "m_TableEntryReference": {"m_KeyId": 0, "m_Key": "settings.title"}},
                                 "m_UpdateString": call("tmp:1")}},
        {"id": "e:2", "fields": {"m_StringReference": {"m_TableReference": {"m_TableCollectionName": "GUID:abcd"},
                                                       "m_TableEntryReference": {"m_KeyId": 8}},
                                 "m_UpdateString": call("tmp:2")}},
        {"id": "e:3", "fields": {}}])
    buf = io.StringIO()
    with redirect_stdout(buf):
        ul.main([t, "--locale", "tr"])
    out = json.loads(buf.getvalue())
    check("key referenced by name resolves through the shared table", out["texts"].get("tmp:1") == "Ayarlar")
    check("key referenced by id and table by GUID resolves", out["texts"].get("tmp:2") == "Oyna")
    check("an event without values is counted, not guessed", out["unresolved"] == 1)

sys.exit(1 if fails else 0)
