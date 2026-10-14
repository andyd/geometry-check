"""Fixture suite: one broken sketch per check, built next to the assertion it must satisfy.

Runs inside Fusion (anything that calls run(context): the Scripts dialog, or the Fusion MCP script tool
with REPO = '<path to this repo>' prepended). Opens a scratch design, builds every fixture, scans each
through the real registry + scanner, and raises if any check misses its fixture or flags a decoy.
The scratch design is closed on success and left open on failure for inspection.
"""
import math
import os
import sys

import adsk.core
import adsk.fusion

REPO = globals().get('REPO') or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = adsk.core.Point3D.create


def a8_corner_fixture(root):
    """Not mostly square, so corners only. Expect 4 findings: three corners and one culprit line."""
    sk = root.sketches.add(root.xYConstructionPlane)
    sk.name = 'Fixture A8 corners'

    def corner(x, a_deg, b_deg):  # two 5 cm lines from a shared point at (x, 0)
        lines = sk.sketchCurves.sketchLines
        end = lambda deg: P(x + 5 * math.cos(math.radians(deg)), 5 * math.sin(math.radians(deg)), 0)
        a = lines.addByTwoPoints(P(x, 0, 0), end(a_deg))
        return a, lines.addByTwoPoints(a.startSketchPoint, end(b_deg))

    corner(0, 10, 99.6)                      # FLAG: 89.60°, off by 0.40°
    a, b = corner(10, 30, 120)               # square + Perpendicular constraint: no flag
    sk.geometricConstraints.addPerpendicular(a, b)
    corner(20, 50, 139.4)                    # 89.40° is 0.60° off, outside the 0.5° default: no flag
    a, b = corner(30, 65, 154.6)             # 0.40° off, but one line is construction: no flag
    b.isConstruction = True
    corner(40, 90.2, 179.9)                  # FLAG: 0.30° off, directions straddle the 0°/180° wrap
    a, b = corner(60, 20, 110.3)             # FLAG once: b is 0.30° off square with both a and c,
    c = sk.sketchCurves.sketchLines.addByTwoPoints(  # so it is reported as the one line to fix
        b.endSketchPoint, P(b.endSketchPoint.geometry.x + 5 * math.cos(math.radians(20)),
                            b.endSketchPoint.geometry.y + 5 * math.sin(math.radians(20)), 0))
    a = sk.sketchCurves.sketchLines.addByTwoPoints(P(80, 0, 0), P(80 + 5 * math.cos(math.radians(20)),
                                                                 5 * math.sin(math.radians(20)), 0))
    sk.sketchCurves.sketchLines.addByTwoPoints(    # FLAG: corner 0.45° off, lines 0.05 mm short of meeting
        P(80.005, 0, 0), P(80.005 + 5 * math.cos(math.radians(110.45)), 5 * math.sin(math.radians(110.45)), 0))
    return sk, ['off square by 0.40°', 'off square by 0.30°', 'off square with 2 touching lines',
                'off square by 0.45°']


def a8_grid_fixture(root):
    """Mostly horizontal/vertical, so the grid pass runs. Expect 2 findings, one per tilted line."""
    sk = root.sketches.add(root.xYConstructionPlane)
    sk.name = 'Fixture A8 grid'
    lines = sk.sketchCurves.sketchLines
    tan = lambda deg: math.tan(math.radians(deg))
    bottom = lines.addByTwoPoints(P(0, 0, 0), P(10, 0, 0))
    right = lines.addByTwoPoints(bottom.endSketchPoint, P(10 + 5 * tan(0.3), 5, 0))  # FLAG: 0.30° off vertical
    top = lines.addByTwoPoints(right.endSketchPoint, P(0, 5, 0))
    lines.addByTwoPoints(top.endSketchPoint, bottom.startSketchPoint)
    for y in (0, 2, 4):                                                    # square lines: the majority
        lines.addByTwoPoints(P(20, y, 0), P(30, y, 0))
    lines.addByTwoPoints(P(35, 0, 0), P(35, 5, 0))
    lines.addByTwoPoints(P(40, 0, 0), P(50, 10 * tan(0.2), 0))             # FLAG: touches nothing, 0.20° off
    lines.addByTwoPoints(P(60, 0, 0), P(65, 5, 0))                         # 45°: not near the grid, no flag
    lines.addByTwoPoints(P(70, 0, 0), P(70 + 5 * tan(1), 5, 0))            # 1° off, outside tolerance: no flag
    c = lines.addByTwoPoints(P(80, 0, 0), P(90, 10 * tan(0.1), 0))         # construction: no flag
    c.isConstruction = True
    return sk, ['0.30° off vertical', '0.20° off horizontal']


def a9_fixture(root):
    """Expect exactly 3 findings: a 0.05 mm gap, a touching-but-unjoined pair, an almost-closed arc."""
    sk = root.sketches.add(root.xYConstructionPlane)
    sk.name = 'Fixture A9'
    lines = sk.sketchCurves.sketchLines
    l1 = lines.addByTwoPoints(P(0, 0, 0), P(5, 0, 0))
    l2 = lines.addByTwoPoints(l1.endSketchPoint, P(5, 3, 0))              # shared point: no flag
    l3 = lines.addByTwoPoints(P(5.005, 3, 0), P(0, 3, 0))                 # FLAG: 0.05 mm from l2's end
    lines.addByTwoPoints(l3.endSketchPoint, P(0, 0.05, 0))               # 0.5 mm from l1, outside tolerance: no flag
    c = lines.addByTwoPoints(P(10, 0, 0), P(10, 5, 0))
    c.isConstruction = True
    lines.addByTwoPoints(P(10.005, 5, 0), P(12, 5, 0))                   # 0.05 mm from construction: no flag
    lines.addByTwoPoints(P(20, 0, 0), P(20.005, 0, 0))                   # tiny segment's own ends (A5's job): no flag
    lines.addByTwoPoints(P(30, 0, 0), P(32, 0, 0))
    lines.addByTwoPoints(P(32, 0, 0), P(32, 2, 0))                       # FLAG: touching, never joined
    a = lines.addByTwoPoints(P(40, 0, 0), P(42, 0, 0))
    b = lines.addByTwoPoints(P(42.003, 0, 0), P(42, 2, 0))
    sk.geometricConstraints.addCoincident(a.endSketchPoint, b.startSketchPoint)  # joined: no flag
    a = lines.addByTwoPoints(P(50, 0, 0), P(52, 0, 0))                   # chained joins: a-b and b-c
    b = lines.addByTwoPoints(P(52.003, 0, 0), P(52, 2, 0))               # make a-c joined too: no flag
    c = lines.addByTwoPoints(P(51.998, 0.002, 0), P(54, 1, 0))
    sk.geometricConstraints.addCoincident(a.endSketchPoint, b.startSketchPoint)
    sk.geometricConstraints.addCoincident(b.startSketchPoint, c.startSketchPoint)
    arcs = sk.sketchCurves.sketchArcs
    arcs.addByCenterStartSweep(P(60, 10, 0), P(61, 10, 0), 2 * math.pi - math.radians(0.2))  # FLAG: 0.035 mm short
    arcs.addByCenterStartSweep(P(70, 10, 0), P(70.005, 10, 0), math.pi / 2)  # tiny arc's own ends: no flag
    return sk, ['0.05 mm apart', 'touch but are not joined', "curve's two ends are 0.0349"]


def world_coords_case(design, scanner):
    """Locate must land in world space: sketch on the XZ plane, inside a sub-component moved +100 cm in x.
    The A9 gap sits at sketch (5.0025, 3), so its world center is x = 105.0025, y = 0, |z| = 3."""
    move = adsk.core.Matrix3D.create()
    move.translation = adsk.core.Vector3D.create(100, 0, 0)
    comp = design.rootComponent.occurrences.addNewComponent(move).component
    sk = comp.sketches.add(comp.xZConstructionPlane)
    sk.name = 'Fixture world coords'
    lines = sk.sketchCurves.sketchLines
    lines.addByTwoPoints(P(0, 3, 0), P(5, 3, 0))
    lines.addByTwoPoints(P(5.005, 3, 0), P(5, 6, 0))
    found = [f for f in scanner.scan(design, {}, [sk]) if f.check_id == 'A9']
    x, y, z = found[0].viewport_hint['center'] if len(found) == 1 else (None,) * 3
    ok = x is not None and abs(x - 105.0025) < 1e-6 and abs(y) < 1e-6 and abs(abs(z) - 3) < 1e-6
    print(f"{'PASS' if ok else 'FAIL'} world coords: {len(found)} finding(s), center {[x, y, z]}")
    return ok


def a1_fixture(root):
    """Expect exactly 2 findings: the U-shape's two open tips. The rest are decoys."""
    sk = root.sketches.add(root.xYConstructionPlane)
    sk.name = 'Fixture A1'
    lines = sk.sketchCurves.sketchLines
    lines.addTwoPointRectangle(P(0, 0, 0), P(5, 5, 0))                    # closed: no flag
    u1 = lines.addByTwoPoints(P(10, 5, 0), P(10, 0, 0))                   # FLAG: U-shape, open at both tips
    u2 = lines.addByTwoPoints(u1.endSketchPoint, P(14, 0, 0))
    lines.addByTwoPoints(u2.endSketchPoint, P(14, 5, 0))                  # FLAG (this line's far end)
    g1 = lines.addByTwoPoints(P(20, 0, 0), P(24, 0, 0))                   # hairline pair: A9's, not A1's
    g2 = lines.addByTwoPoints(P(24.005, 0, 0), P(24, 4, 0))
    lines.addByTwoPoints(g2.endSketchPoint, g1.startSketchPoint)          # close their far ends
    c = lines.addByTwoPoints(P(30, 0, 0), P(34, 0, 0))
    c.isConstruction = True                                               # construction: no flag
    sk.sketchCurves.sketchCircles.addByCenterRadius(P(40, 2, 0), 2)       # circle, no endpoints: no flag
    t = lines.addByTwoPoints(P(2.5, 2, 0), P(2.5, 3, 0))                  # both ends tied onto rectangle edges
    bottom = next(l for l in (lines.item(i) for i in range(4)) if l.startSketchPoint.geometry.y == 0 and l.endSketchPoint.geometry.y == 0)
    top = next(l for l in (lines.item(i) for i in range(4)) if l.startSketchPoint.geometry.y == 5 and l.endSketchPoint.geometry.y == 5)
    sk.geometricConstraints.addCoincident(t.startSketchPoint, bottom)
    sk.geometricConstraints.addCoincident(t.endSketchPoint, top)
    return sk, ['Open endpoint', 'Open endpoint']


def a1_scatter_fixture(root):
    """10 loose segments = 20 open endpoints: expect one summary, not a flood."""
    sk = root.sketches.add(root.xYConstructionPlane)
    sk.name = 'Fixture A1 scatter'
    for i in range(10):
        sk.sketchCurves.sketchLines.addByTwoPoints(P(i * 3, 0, 0), P(i * 3 + 2, 1, 0))
    return sk, ['20 open endpoints']


def a5_fixture(root):
    """Expect exactly 1 finding: a 0.05 mm sliver in a ~10 cm sketch. The rest are decoys."""
    sk = root.sketches.add(root.xYConstructionPlane)
    sk.name = 'Fixture A5'
    lines = sk.sketchCurves.sketchLines
    lines.addTwoPointRectangle(P(0, 0, 0), P(10, 10, 0))
    lines.addByTwoPoints(P(3, 5, 0), P(3.005, 5, 0))                      # FLAG: 0.05 mm sliver
    lines.addByTwoPoints(P(6, 5, 0), P(6.2, 5, 0))                        # 2 mm: above threshold, no flag
    c = lines.addByTwoPoints(P(8, 5, 0), P(8.005, 5, 0))
    c.isConstruction = True                                               # construction sliver: no flag
    return sk, ['Tiny segment: only 0.05 mm']


CASES = [('A1', a1_fixture), ('A1', a1_scatter_fixture), ('A5', a5_fixture),
         ('A8', a8_corner_fixture), ('A8', a8_grid_fixture), ('A9', a9_fixture)]


def fix_cases(app, scanner, fixer):
    """Experimental Fix: every fix offered on a fixture must apply and verify. Each runs on a fresh copy
    (no command transaction here to roll a failure back). Returns failure descriptions."""
    failures = []
    for check_id, build in CASES:
        count = None
        k = 0
        while count is None or k < count:
            doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
            design = adsk.fusion.Design.cast(app.activeProduct)
            sketch, _ = build(design.rootComponent)
            found = scanner.scan(design, {}, [sketch])
            count = len(found)
            if k < count and found[k].fix:
                ok, msg = fixer.apply_and_verify(design, found[k], {})
                print(f"{'PASS' if ok else 'FAIL'} fix {sketch.name} #{k}: {found[k].message[:40]}... -> {msg[:80]}")
                if not ok:
                    failures.append(f'fix {sketch.name} #{k}')
            doc.close(False)
            k += 1
    return failures


def ignore_case(app, scanner):
    """Ignore marks: persist through rescans, only hide the marked finding, and restore cleanly."""
    doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    sketch, _ = a9_fixture(design.rootComponent)
    found = scanner.scan(design, {}, [sketch])
    target = found[0]
    scanner.mark_intended(target)
    after = scanner.scan(design, {}, [sketch])
    hidden = [f for f in after if f.ignored]
    ok1 = len(hidden) == 1 and hidden[0].key == target.key and len(after) == len(found)
    scanner.unmark_intended(hidden[0])
    ok2 = not any(f.ignored for f in scanner.scan(design, {}, [sketch]))
    print(f"{'PASS' if ok1 and ok2 else 'FAIL'} ignore/restore: hidden {len(hidden)}, restored clean {ok2}")
    doc.close(False)
    return ok1 and ok2


def run(_context):
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    for m in [m for m in sys.modules if m == 'GeometryCheck' or m.startswith('GeometryCheck.')]:
        del sys.modules[m]  # pick up edits without restarting Fusion
    from GeometryCheck.engine import fixer, scanner

    app = adsk.core.Application.get()
    doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    design = adsk.fusion.Design.cast(app.activeProduct)
    design.fusionUnitsManager.distanceDisplayUnits = adsk.fusion.DistanceUnits.MillimeterDistanceUnits

    failures = []
    for check_id, build in CASES:
        sketch, expected = build(design.rootComponent)
        found = [f for f in scanner.scan(design, {}, [sketch]) if f.check_id == check_id]
        msgs = [f.message for f in found]
        ok = len(found) == len(expected) and all(any(e in m for m in msgs) for e in expected)
        print(f"{'PASS' if ok else 'FAIL'} {check_id} ({sketch.name}): {len(found)} finding(s), expected {len(expected)}")
        for m in msgs:
            print('   -', m)
        if not ok:
            failures.append(sketch.name)

    if not world_coords_case(design, scanner):
        failures.append('world coords')
    failures += fix_cases(app, scanner, fixer)
    if not ignore_case(app, scanner):
        failures.append('ignore/restore')

    if failures:
        raise AssertionError(f'Fixture failures: {failures}. Scratch design left open for inspection.')
    doc.close(False)
    print('All fixtures pass.')
