# Unity Reverse-Engineering Guide

Unity ships game logic as native IL2CPP or as managed Mono assemblies. jadx is
blind to IL2CPP — detect the build first with `detect-unity.sh`.

## IL2CPP (`detect-unity.sh` → `il2cpp`)

Inputs: `lib/<abi>/libil2cpp.so` + `assets/bin/Data/Managed/Metadata/global-metadata.dat`.
Run `il2cpp-dump.sh <so> <metadata> <out>` (wraps **Il2CppInspectorRedux**,
https://github.com/LukeFZ/Il2CppInspectorRedux, needs .NET).

**Recoverable:** class / method / field / enum signatures, type hierarchy,
serialized fields, network/RPC type shapes → data model + feature inventory.
**Not recoverable:** C# method *bodies* (compiled to native ARM in the .so).

## Mono (`detect-unity.sh` → `mono`)

Inputs: `assets/bin/Data/Managed/*.dll` (real .NET assemblies). Decompile to
near-source C# with `ilspycmd` (ILSpy CLI): `ilspycmd Assembly-CSharp.dll -o <out>`.
Best case — full logic recovered.

## Assets (both branches)

`unity-assets.sh <apk> <out>` wraps **AssetRipper**
(https://github.com/AssetRipper/AssetRipper). Extracts textures, sprites, UI
atlases, fonts, audio, shaders, **scenes, prefabs** → the game's design system.
Play screenshots are also downloaded to `$WORK/screenshots/` (via
`scrape-play-store.py`) and are the **primary layout reference** for Unity since
Android `res/` is absent.

## Graceful degradation

If a tool is absent, its wrapper exits 3 with install guidance. The subagent
then writes a partial `unity-digest.md` and sets `RE Method: limited: unity-no-tools`.

## Legal

Extracted game art is copyrighted. Outside authorized use (own game, lawful
research), treat extracted assets as **reference only** and recreate in the same
style — do not ship them.

## Game mechanics & formulas (fidelity pass)

In the Phase 8 fidelity pass, deepen `$WORK/unity-digest.md` beyond the type
model + netcode to capture the playable rules:

- **Game mechanics** — core loop, win/lose conditions, level/wave progression,
  player/enemy state machines (from the C# `MonoBehaviour` methods).
- **Formulas** — damage/score/economy/cooldown calculations, drop rates, curve
  tables (constants and arithmetic in the decompiled C#).
- **Tunables** — `ScriptableObject` configs and serialized fields that balance
  the game.

Confidence: Unity **mono** is near-source (high); **il2cpp** gives signatures +
partial bodies (med). State the level reached.
