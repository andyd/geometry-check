"""A1: open profile endpoints. An endpoint connected to nothing: the clearly-open case.

Distinct from A9: A9 catches endpoints that *almost* meet another one (looks closed, isn't); A1 catches
the ones with no partner anywhere near. Endpoints A9 already covers are excluded here, so the two checks
never report the same point twice.
"""
import math

from ..base import Finding
from . import a9_hairline_gaps as a9

id = 'A1'
name = 'Open profile endpoints'
category = 'sketch'
severity = 'warning'
scope = 'sketch'

MAX_INDIVIDUAL = 8  # more open endpoints than this in one sketch reads as an intentionally open sketch
                    # (a sweep path, laser-cut line art): summarize instead of flooding the panel


def detect(ctx):
    findings = []
    for sketch in ctx.sketches:
        points, by_loc, lengths, refs = a9._endpoints(sketch)
        if not points:
            continue
        coords = {k: (sp.geometry.x, sp.geometry.y, curves) for k, (sp, curves) in enumerate(points)}
        xs, ys = [c[0] for c in coords.values()], [c[1] for c in coords.values()]
        diag = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
        if ctx.check_enabled('A9'):
            # A9's ACTUAL tolerance decides which check owns a borderline point: never both, never neither
            g = ctx.params_for('A9')
            near_eps = max(g['gap_mm'] / 10.0, g['gap_pct'] / 100.0 * diag, 1e-9)
            near = {k for pair in a9.hairline_pairs(coords, near_eps,
                                                    a9._join_groups(sketch, points, by_loc), lengths)
                    for k in pair}
        else:
            near = set()  # A9 is off: nobody else reports hairline pairs, so their endpoints are open here
        constrained = set()  # any Coincident touching a point counts as connected (incl. point-on-curve)
        for c in sketch.geometricConstraints:
            if c.objectType != a9.COINCIDENT:
                continue
            for ent in (c.point, c.entity):
                k = a9._index(ent, points, by_loc)
                if k is not None:
                    constrained.add(k)
        opens = [k for k, (sp, curves) in enumerate(points)
                 if len(curves) == 1 and k not in constrained and k not in near and not (curves & refs)]
        if len(opens) > MAX_INDIVIDUAL:
            findings.append(_summary(ctx, sketch, [points[k][0] for k in opens]))
        else:
            findings += [_finding(ctx, sketch, points[k][0], lengths[next(iter(points[k][1]))]) for k in opens]
    return findings


def _finding(ctx, sketch, sp, curve_len):
    w = ctx.to_world(sketch, sp.geometry)
    return Finding(
        check_id=id,
        severity=severity,
        message=('Open endpoint: nothing connects here, so a profile through this point cannot close '
                 'and will not extrude. Close it with a line, or drag it onto another endpoint.'),
        entities=[sp],
        viewport_hint={'center': w, 'extent': max(1.5 * curve_len, 0.5), 'segments': []},
    )


def _summary(ctx, sketch, sps):
    pts = [ctx.to_world(sketch, sp.geometry) for sp in sps]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return Finding(
        check_id=id,
        severity='info',
        message=(f'{len(sps)} open endpoints in this sketch. That usually means it is intentionally open '
                 '(a path or line art). If so, ignore this; if it should be closed outlines, it has gaps.'),
        entities=sps[:20],
        viewport_hint={'center': [(a + b) / 2 for a, b in zip(lo, hi)],
                       'extent': max(math.dist(lo, hi) * 1.2, 1.0), 'segments': []},
    )
