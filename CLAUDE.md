# Geometry Check (Fusion 360 add-in)

Repo: https://github.com/andyd/geometry-check · Detect-first: finds slightly-wrong sketch geometry,
explains it in plain language, locates it in the viewport. Fixes are opt-in and verified.

## Project Tracking

| Field | Value |
|-------|-------|
| **Category** | Fusion 360 Add-in (Python) |
| **Status** | 🔵 Active (public alpha) |
| **Last Worked** | Oct 13, 2026 |
| **Next Action** | Alpha launch posts; then A2 duplicates / A3 self-intersection + geometry snapshot |

## Working rules

- **Bump `version` in `GeometryCheck/GeometryCheck.manifest` with every change to the add-in** (patch for
  fixes, minor for features), commit, then tag: `git tag -a vX.Y.Z -m "Geometry Check vX.Y.Z" && git push
  && git push origin vX.Y.Z`. Manifest version, git tag, and the palette title (read at load) always
  match. Docs-only changes outside `GeometryCheck/` don't bump.
- Add-in lives in `GeometryCheck/` (folder, .py, .manifest names must match).
- Checks: `GeometryCheck/checks/<category>/*.py`, registered in `checks/registry.py`.
- Fixtures + assertions: `tests/run_fixtures.py`, run inside Fusion (Fusion MCP `script` tool works).

## Fusion API pitfalls (learned the hard way)

- Fusion MCP scripts auto-terminate: event handlers (commands, palette) die when the script returns
  unless the script calls `adsk.autoTerminate(False)`. Real use: load via Scripts and Add-Ins.
- A Fusion MCP script that raises is rolled back (geometry it created disappears).
- Fusion loads add-ins with `__package__ = None` (module name like `__main__%2F...GeometryCheck_py`);
  don't build import names from `__package__` (crashed startup once; reverted).
- Never create and delete the palette inside one script, then call `Viewport.refresh()`: refresh pumps
  the UI event loop and a pending timer on the dead palette crashed Fusion. See highlight.clear.
- `entityToken` strings are stable across rescans of an unmodified design but CHANGE after any edit.
  `Finding.key` is therefore panel-session identity only; persistent marks (Ignore) are stored as
  Fusion **attributes on the entities** (group `GeometryCheck`), which travel with the geometry.

## Experimental fixes

- `Finding.fix` is an optional `() -> str` closure; `engine/fixer.apply_and_verify` applies it and
  re-scans. The hidden `GeometryCheckApplyFix` command runs fix/ignore/restore so each is one undo
  step; a failed verify sets `executeFailed`, which aborts the transaction.
- Fusion's solver chooses what moves. Grid fixes lock already-square touching lines first; the culprit
  fix holds one neighbor `isFixed` while constraining, then releases it. Almost-closed curves get no fix.
- `fix_cases` in the fixture suite asserts every offered fix verifies, each on a fresh copy.

## Known small gaps / open questions

- Grid broadphase can miss a pair at exactly the tolerance (float rounding); in an A-B-C-D chain of
  off-square lines, the middle lines are reported twice.
- A8 T-junctions: the corner pass only pairs lines sharing/nearly-sharing an endpoint; a line ending
  mid-way along another isn't a corner yet.
- A8 pass 3: lines neither near the square grid nor touching another line are not compared yet.
- Before M2 (body checks): per-sketch geometry snapshot (perf + pytest-able checks), Ctx scope passes,
  cross-linking via `Finding.linked_findings` keys.
