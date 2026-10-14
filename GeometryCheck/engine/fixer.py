"""Experimental Fix: apply a finding's fix, then check it really helped.

apply_and_verify() applies the fix and reports whether to keep it. The caller rolls back a failed fix: the
Fix command sets executeFailed, which aborts its transaction, so the design is left exactly as it was.
"""
import adsk.fusion

from . import scanner


def apply_and_verify(design, finding, settings):
    """Returns (ok, message). ok=False means the caller must roll back."""
    # Contract: every fix-carrying finding is a sketch finding whose entities live in one sketch.
    # Body-check fixes, when they exist, will need their own verification scope here.
    if not finding.entities or not hasattr(finding.entities[0], 'parentSketch'):
        return False, 'This fix has no sketch to verify against; nothing was changed.'
    sketch = finding.entities[0].parentSketch
    before = scanner.scan(design, settings, [sketch])
    broken_before = _broken_features(design)
    try:
        done = finding.fix()
    except RuntimeError as e:
        return False, (f"Fusion couldn't add the constraint ({_first_line(e)}). A dimension or another "
                       'constraint probably holds this geometry. Nothing was changed.')
    after = scanner.scan(design, settings, [sketch])
    if any(_same(finding, g) for g in after):
        return False, 'The constraint went on but the problem was still there, so it was undone.'
    new = [g for g in after if not any(_same(g, b) for b in before)]
    if new:
        return False, f'Undone: this fix would have created a new problem. {new[0].message}'
    if _broken_features(design) > broken_before:
        return False, 'Undone: a feature built from this sketch failed to rebuild after the fix.'
    return True, done


def _same(f, g):
    """Same finding: same check, same entities (order-free)."""
    return (f.check_id == g.check_id and len(f.entities) == len(g.entities)
            and all(any(e == x for x in g.entities) for e in f.entities))


def _broken_features(design):
    error = adsk.fusion.FeatureHealthStates.ErrorFeatureHealthState
    timeline = design.timeline
    return sum(1 for i in range(timeline.count) if timeline.item(i).healthState == error)


def _first_line(e):
    return str(e).strip().splitlines()[-1] if str(e).strip() else type(e).__name__
