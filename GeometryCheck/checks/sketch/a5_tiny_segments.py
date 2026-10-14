"""A5: tiny segments. Sliver curves far below the sketch's scale: debris that breaks offsets and shells.

Threshold is relative to the sketch's own size (default 0.1% of its diagonal) so legitimate small features
on small parts are not flagged. Info severity: slivers are sometimes deliberate.
"""
import math

from ..base import Finding, midpoint
from . import a9_hairline_gaps as a9

id = 'A5'
name = 'Tiny segments'
category = 'sketch'
severity = 'info'
scope = 'sketch'
params = {'len_pct': (0.1, 'Max length (% of sketch diagonal)', (0.01, 1.0, 0.01))}


def detect(ctx):
    findings = []
    for sketch in ctx.sketches:
        points, _, lengths, refs = a9._endpoints(sketch)
        if not points:
            continue  # ponytail: curves without endpoints (lone circles) aren't measured; tiny circles are rare debris
        xs = [sp.geometry.x for sp, _ in points]
        ys = [sp.geometry.y for sp, _ in points]
        diag = math.hypot(max(xs) - min(xs), max(ys) - min(ys))
        eps = ctx.params['len_pct'] / 100.0 * diag
        for ci, length in lengths.items():
            if 0 < length < eps and ci not in refs:
                findings.append(_finding(ctx, sketch, sketch.sketchCurves.item(ci), length, eps))
    return findings


def _finding(ctx, sketch, curve, length, eps):
    wa = ctx.to_world(sketch, curve.startSketchPoint.geometry)
    wb = ctx.to_world(sketch, curve.endSketchPoint.geometry)
    return Finding(
        check_id=id,
        severity=severity,
        message=(f'Tiny segment: only {ctx.fmt_len(length)} long (threshold {ctx.fmt_len(eps)}). Slivers '
                 'like this break offsets, shells, and exports. If it is debris, delete it; if it is '
                 'deliberate, lower the A5 threshold in Settings.'),
        entities=[curve],
        viewport_hint={'center': midpoint(wa, wb), 'extent': max(length * 20, 0.1), 'segments': [[wa, wb]]},
    )
