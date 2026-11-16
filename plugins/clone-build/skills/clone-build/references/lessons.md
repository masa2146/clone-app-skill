# Lessons from two shipped clones

Two Unity mobile games went from extraction to store release with this pipeline (one
physics game, one puzzle game with ~2,000 levels). This file is what cost days in
them that the task list did not prevent. Each item: **rule** — what happened (one
scene) — how to check. The `T…` ids are the lifecycle rows (`templates/lifecycle.tsv`)
the rule belongs to; read the section of a phase when its first task starts.

Everything already enforced by a script (node-tree import, `check-extraction`, stale
delivery, level referees) is not repeated here.

## F0 Decisions — the first day

1. **Start the slow external clocks on day one** (T001, T002). Personal Play accounts
   need a closed test of 12 testers × 14 days before production; App Store purchases
   and EU distribution stay locked until the paid-apps agreement (bank + tax forms) and
   the EU trader declaration are signed — only the account holder can do those, and they
   take days. Both projects found them late: one's first upload waited 12 days after
   the forms were done; the other noticed the agreement on the day of its first
   submission. *Check:* KARARLAR lists the
   dates; the first internal-test upload happens as soon as anything installs.
2. **Check the name on both stores before falling in love with it** (T001). The wanted
   name was taken on the App Store; the iOS listing had to ship under a variant.
   *Check:* search both stores, record the exact listing name per store.
3. **Decide "will this ship?" before the first commit** (T001). Extracted art committed
   once never leaves the history. Keep extraction outside the repo (kur does this); if a
   faithful-copy branch ever carries extracted files, see #15 and #49.
4. **Raise transcript retention** (T003). The default keeps 30 days; one project lost
   its first month of session history. *Check:* `cleanupPeriodDays` ≥ 365 in the user's
   Claude settings (`preflight.sh` reports it).

## F1 Setup

5. **One task, one worktree, deleted on merge** (T004). Two sessions in one folder: one
   switched branches and the other's commit landed on the wrong branch. Worktrees fixed
   that, but nobody removed them: 15 merged worktrees held 85 GB, because each Unity
   `Library` diverges from its APFS clone as soon as Unity re-imports. *Check:*
   `tasks.py next --worktree` for parallel work, `tasks.py temizle --yes` after merges,
   `tasks.py disk` in `/task durum`.
6. **Parallel sessions talk to each other, not through the user** (T004). The user
   copied prompts, approvals and merge notices between sessions dozens of times. If the
   agent runtime has cross-session messaging, use it; the status doc has a "parallel
   work" table where each session edits only its own row; whoever merges to main tells
   the other session first.
7. **Disk is a budget, measured with `df`** (T014). The big eaters were outside the
   repos: every iOS simulator runtime Xcode ever installed (7 runtimes, 55 GB),
   DerivedData (12 GB), five Android NDKs Unity never used (it ships its own, 14 GB),
   system images with no emulator, PNG frame sequences already encoded to mp4 (~24 GB by `du` in
   one project), an xcarchive per upload. `du` counts APFS clones in full: a measurement
   copy "14 GB" by `du` freed 0.17 GB (the frame figure above is also a `du` estimate). *Rule:* capture scripts delete their frames after
   encoding; keep only the live and the latest build; logs go under `Logs/`; keep the
   simulator runtimes and NDKs you named in KARARLAR. Never try `--help` on a cleanup
   tool you have not read — an old version took `--help` as "clean now".
8. **Heavy jobs need a lock** (T014). With other Unity editors open, tests timed out and
   captures ran 3–4× slow; a red test was "machine under load" more than once. *Check:*
   before reading a red, ask whether another heavy job ran.
9. **Tests and captures never use the player's save** (T014). Editor, tests and capture
   arms shared one save file; one wrote and did not restore, the next test saw stale
   coins. Use a temporary save folder.
10. **One adb, the one from the SDK that runs the emulator / Unity** (T006). Two adb
    versions kicked each other's server off all day.

## F2 Source

11. **Videos are evidence only after you match the board, not the number** (T008). A
    channel's HUD was one ahead from some level on; CDN-delivered chapters reuse numbers
    for different layouts. Match by structure. Download the highest resolution (the
    default pick was 288p while 1080p existed).
12. **Read dumps by object id, not by name** (T009). A display ball with the same name as
    the thrown one was read: the thrown ball came out 25× heavier. Names collide (4
    materials with one name in one package).
13. **The runtime profile wins over the project settings** (T009). The source game
    changed physics rate and solver iterations at start-up on Android and ran extra
    solver steps while loading. A simulation that skips the start-up path gives false
    results: 57 levels "crashed" in a sweep; the phone disproved it the next day.
14. **Prove a rule by counting** (T010). "Total ammo = painted health + stock" either
    balances on every level or it is not the rule. One reading that holds on dozens of
    levels beats any guess; if the data balances and the game does not, the bug is ours.
15. **Freeze the faithful copy before you replace anything** (T016). The last
    state that looked exactly like the original became a protected branch + tag. A git
    `reference-transaction` hook refuses every update or delete of that ref; a bundle
    backup lives outside the repo; the branch is never pushed (it carries extracted
    art). Every later "how did the original do this?" was answered from it.

## F3–F5 Direction, vertical slice, look lock

16. **The phone on week one** (T006, T012). The first device day found seven bugs the
    editor hid. Every visual task is seen once on the phone: a text-outline material that
    was right in the editor fell back to a default shader in the build, so all outlines
    vanished on device.
17. **Recording changes what you measure** (T005). Adaptive quality lowered the physics
    rate while recording; a capture helper covered what it photographed; a translucent UI
    was captured 7× darker; batch capture hung for hours when the screen slept
    (`caffeinate -d`). Physics is not deterministic: compare "what the debris looks
    like", not "where it landed".
18. **Readability before beauty** (T013). Players failed on what they could not read,
    not on what looked plain. Big glow "hurts the eyes"; liveliness comes from shape.
19. **Design permanent pieces in the game frame** (T013). A tower drawn alone in a 3/4
    view and turned into a model looked "terrible" in the game camera. Target images are
    made on top of a real game frame, at real size, in the game's camera.
20. **Images from an image model, cut by code — not drawn by code** (T013, T071). Code-
    drawn icons and level pictures were judged "not professional, not sharp, all the
    same". Generating them in the game's palette with three-tone shading and a different
    style per level, then reading them into the grid by code, fixed it.
21. **Colour-blind check** (T013). Green and yellow were near-identical for a red-green
    colour-blind player (ΔE 82 → 9); found by accident. A design that depends on those two
    colours needs a shape cue.

## F6–F8 Mechanics, screens, meta

22. **Every state transition has a test** (T081). After buying "continue" with
    coins the level froze: the lose state never handed control back to play. Win, lose,
    continue-with-ad, continue-with-coins, quit, background/resume — each is one test.
23. **Fake store pays late, like the real one** (T091). The editor's fake store paid
    instantly; the phone paid later, the screen did not refresh, and paying players saw
    locked rows in production. The fake store gets a delayed-approval mode and tests wait.
24. **Taps arrive faster than animations** (T080). A double tap ran one move twice. A
    per-action tap guard and a "N taps per second" test.
25. **Safe area on every screen root, backgrounds bleed** (T030). The title was bound to
    the safe area, the content to the raw screen: on a notched phone the title covered the
    first row; on a tall iPhone the bottom bar floated. Capture 10+ aspect ratios, 20:9 and
    tablet included.
26. **A screen that hides but stays active runs `OnEnable` once** (T030). A new screen
    missing from the hand-kept screen list let Back open the quit dialog over it.
27. **Feedback rounds on the phone are planned, not accidental** (T035, T130). One round of
    the user playing the release build produced a dozen fixes (current level on the home
    screen, first-launch ad rule, heart timer, button sound, dead menu colours). Thresholds
    like "no ad before the Nth launch" live in remote config so they change without a
    release.

## F9 Art and sound

28. **Count the originals left in the build, every day** (T050). The first package scan
    found a forgotten font and an invisible collision mesh.
29. **A paid shader needs a licence row before the store** (T050, T110). In one project
    hundreds of materials depended on a paid shader whose licence was left for "after
    launch"; in the other, 25 materials used one with no licence record at all. Either buy it
    before the first store upload or write your own and prove it with ΔE per material.
30. **CC BY music needs a credit screen** (T060). Prefer CC0; for CC BY add the credit in
    settings and a `LICENSES.tsv` row.
31. **Fonts: Turkish and Cyrillic glyphs, or a fallback** (T061). Missing "ğ ş İ" was found
    in a screenshot, Cyrillic only when a third language went in.
32. **Original texts and icon language are part of the scan** (T111). Package names,
    taglines and the original's icon motifs (crowns, crests) survived until a text audit.

## Unity traps (any phase)

33. **Generated scenes keep old values** (T120). A new `[SerializeField]` default does
    nothing until the scene is regenerated, and a store build packs the stale scene. Run
    the scene builder before every release build.
34. **`NewScene` in an editor script empties a reference saved a moment ago** (T060).
    Ball and floor sounds were silent for 8 days. Load by path, and a guard test reads the
    serialized field.
35. **Pass `-buildTarget` to every batch command** (T120). The editor's last platform
    sets the compile symbols: left on iOS, batch tests compiled the store code out and 23
    tests broke; an Android build without it failed with "script class layout is
    incompatible".
36. **A compile error makes the test runner use the old DLL** — unrelated tests go red.
    `grep "error CS"` first.
37. **Builds dirty tracked files** (T120). TMP atlases, Firebase poms, the Crashlytics id,
    URP assets, prefabs. Kur writes the list of files every build regenerates into
    KARARLAR; `bitir` stops if anything else is dirty. Otherwise every task branch drags
    them along.
38. **Splash images are resized to a power of two** (T120): a logo came out 11 % wide.
    Turn scaling off for splash art. Use LZ4 compression for Android builds (the default
    stalled loading).

## F10 Levels

39. **Obstacles first, picture second** (T071). A nicer picture is never a reason to drop
    an obstacle; the source's obstacle mix for the same range is the starting point. The
    order is: obstacle plan → a picture that carries the obstacles' positions.
40. **Every level is beaten by the bot at least once before release** (T072, T110). Six
    levels nobody had ever finished were in the pack.
41. **Strict reviewer loops oscillate** (T072). Seven rounds gave opposite verdicts on the
    same asset. Act on repeated and measured remarks; after ~3 rounds hand it to the user.

## F11–F12 Saves, money, remote content

42. **Version the save; old saves open in the new build** (T080). Changing level 120 in
    1.1 would drop a mid-level save onto a different board.
43. **Verify the purchase signature on the client, test with a licence tester** (T091).
    Unverified receipts are an open door.
44. **Play Billing "code 12 / NETWORK_ERROR" is not the network** (T091): products do not
    exist until an AAB with the billing permission is uploaded. Diagnose from the Play
    Store service lines in logcat.
45. **Remote updates replace what exists; they never add** (T094). Allowed remotely: a
    model, material, texture, sprite, effect or sound that replaces an existing field;
    level files (fixes, and new levels after the last shipped one); whitelisted economy/ad
    numbers with bounds (the server sending 40000 instead of 40 is rejected); an
    announcement; a forced update. Not remote: code, a new mechanic or component, fonts,
    in-game fixed texts, and **a new field on a remotely swapped data object** — one such
    attempt drove Android start-up to 4.4 GB of memory and a crash. Signed manifest +
    fingerprints; download limited by "no bytes for N s", not by total time; the new pack
    activates on the next launch, a broken one falls back to the bundled pack. Every
    publish: dry run → 10 % → full, rollback in one command, each with user approval.
    Raising `minVersion` locks out every older install — only on explicit request.
46. **Free cloud servers expire** (T090, T095). A trial ended and the privacy pages were
    down for hours. Check the billing type and disk backup before release.

## F13–F16 Device QA, store, release

47. **Version numbers: one counter per store, at the top of the status doc** (T120). Two
    sessions built the same version code. Play's version code and the App Store's build
    number are separate counters (in one project 16 vs 5).
48. **Package size is measured from the first phone build** (T101). One project's level
    files alone were 608 MB.
49. **Release scan covers history, not just the package** (T110). `git log --all
    --name-only` against extraction paths and hashes. If it is dirty (or a faithful-copy
    branch exists, #15), publish only a clean single-commit snapshot of `main` to the
    remote and add a pre-push hook that refuses anything else. Previews under the docs
    folder (png/jpg/mp4) stay out of git too — they bloat the repo and dirty the snapshot.
50. **App Store review asks for proof** (T123). The first submission came back with
    "information needed": a screen recording on a real iPhone plus review notes. Have both
    ready at the first submission. Archive unsigned, sign on export, choose manual release.
    Price tiers do not match Play's prices one to one. Keep an upload's xcarchive (dSYM) as
    long as that build is live; delete cancelled ones. In App Store Connect's in-app
    purchase page, leaving without Save loses the input.
51. **Production access answers only what you can prove** (T124): "no crashes/ANRs" only
    with vitals open in another tab.
52. **Store and ad images** (T122 → the `magaza` plugin): 9:16 screenshots (2:1 could not
    enter featured slots), filled tags; raw gameplay crops in ads looked amateur and coin
    bursts got four creatives flagged as gambling.
53. **Release is not the end of discovery** (T130). Organic impressions were near zero for
    28 days. The ad plan is part of the release plan.
54. **The in-app rating prompt** (T130): no gating question in front of it (policy); show
    it only at a good moment (first-try win) and rarely.

If a Play-publishing skill is installed in your environment, it holds the procedures;
this file keeps only the traps and checks.
