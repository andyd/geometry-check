"""A9: hairline gaps. An endpoint within a hair of another curve's endpoint, but not joined to it."""
import math

from ..base import Finding, midpoint

id = 'A9'
name = 'Hairline gaps'
category = 'sketch'
severity = 'error'
scope = 'sketch'
params = {
    'gap_mm': (0.1, 'Gap tolerance (mm)', (0.01, 1.0, 0.01)),
    'gap_pct': (0.05, 'Gap tolerance (% of sketch diagonal)', (0.01, 1.0, 0.01)),
}

COINCIDENT = 'adsk::fusion::CoincidentConstraint'
LOOP_RATIO = 10  # a curve's own two ends are a gap (almost-closed arc/spline) when it is this much longer
                 # than the gap; never true for a line, whose length is the distance between its ends


def detect(ctx):
    findings = []
    for sketch in ctx.sketches:
        points, by_loc, lengths, refs = _endpoints(sketch)
        if len(points) < 2:
            continue
        coords = {k: (sp.geometry.x, sp.geometry.y, curves) for k, (sp, curves) in enumerate(points)}
        xs, ys = [c[0] for c in coords.values()], [c[1] for c in coords.values()]
        diag = math.hypot(max(xs) - min(xs), max(ys) - min(ys))  # of checked endpoints: construction excluded
        eps = max(ctx.params['gap_mm'] / 10.0,  # mm -> cm (Fusion's internal unit)
                  ctx.params['gap_pct'] / 100.0 * diag,
                  1e-9)
        for pair, d in hairline_pairs(coords, eps, _join_groups(sketch, points, by_loc), lengths).items():
            ka, kb = sorted(pair)
            if points[ka][1] | points[kb][1] <= refs:
                continue  # both sides projected: nothing the user can join in this sketch
            same_curve = bool(points[ka][1] & points[kb][1])
            findings.append(_finding(ctx, sketch, points[ka][0], points[kb][0], d, eps, same_curve))
    return findings


def hairline_pairs(points, eps, group, lengths):
    """points: {key: (x, y, curve_ids)}; group: {key: join-group id}; lengths: {curve_id: cm}.
    Returns {frozenset(a, b): distance}: each point's nearest point within eps that is in a different
    join group and on a different curve, or on the same curve when that curve almost closes on itself.
    Grid broadphase with cell size eps."""
    cell = lambda x, y: (math.floor(x / eps), math.floor(y / eps))
    grid = {}
    for k, (x, y, _) in points.items():
        grid.setdefault(cell(x, y), []).append(k)
    pairs = {}
    for k, (x, y, curves) in points.items():
        gx, gy = cell(x, y)
        best = None
        for cx in (gx - 1, gx, gx + 1):
            for cy in (gy - 1, gy, gy + 1):
                for u in grid.get((cx, cy), ()):
                    ux, uy, ucurves = points[u]
                    if u == k or group[k] == group[u]:
                        continue
                    d = math.hypot(ux - x, uy - y)
                    if any(lengths[c] <= LOOP_RATIO * d for c in curves & ucurves):
                        continue  # a short curve's own ends (a tiny line or arc) are A5's business
                    if d <= eps and (best is None or d < best[1]):
                        best = (u, d)
        if best:
            pairs[frozenset((k, best[0]))] = best[1]
    return pairs


def _endpoints(sketch):
    """Unique endpoints of non-construction curves: ([(SketchPoint, {curve index})], location index,
    {curve index: length cm}, {indices of projected/reference curves}).
    Joined curves share one SketchPoint; dedupe by location bucket, then entity equality."""
    points, by_loc, lengths, refs = [], {}, {}, set()
    for ci, curve in enumerate(sketch.sketchCurves):
        if curve.isConstruction:
            continue
        try:
            ends = (curve.startSketchPoint, curve.endSketchPoint)
        except (AttributeError, RuntimeError):
            continue  # circles/ellipses have no endpoints; degenerate curves raise
        lengths[ci] = curve.length
        if curve.isReference:
            refs.add(ci)
        for sp in ends:
            k = _index(sp, points, by_loc)
            if k is None:
                k = len(points)
                points.append((sp, set()))
                by_loc.setdefault(_loc(sp), []).append(k)
            points[k][1].add(ci)
    return points, by_loc, lengths, refs


def _join_groups(sketch, points, by_loc):
    """{point index: group id}. Coincident constraints chain (A-B, B-C joins A-C), so union-find."""
    parent = list(range(len(points)))

    def root(k):
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    for c in sketch.geometricConstraints:
        if c.objectType != COINCIDENT:
            continue
        a, b = _index(c.point, points, by_loc), _index(c.entity, points, by_loc)
        if a is not None and b is not None:
            parent[root(a)] = root(b)
    return {k: root(k) for k in range(len(points))}


def _loc(sp):
    g = sp.geometry
    return round(g.x, 9), round(g.y, 9)


def _index(entity, points, by_loc):
    if not hasattr(entity, 'geometry') or not hasattr(entity.geometry, 'x'):
        return None  # coincident to a curve, not a point
    return next((k for k in by_loc.get(_loc(entity), ()) if points[k][0] == entity), None)


def _finding(ctx, sketch, a, b, d, eps, same_curve):
    wa, wb = ctx.to_world(sketch, a.geometry), ctx.to_world(sketch, b.geometry)
    if same_curve:
        msg = (f'This curve\'s two ends are {ctx.fmt_len(d)} apart (tolerance {ctx.fmt_len(eps)}): it looks '
               'closed but isn\'t. Redraw it closed (an arc as a circle), or close the gap with a short line.')
    elif d > 0:
        msg = (f'Endpoints are {ctx.fmt_len(d)} apart but not joined (tolerance {ctx.fmt_len(eps)}). '
               'It looks closed, but the profile may not be. Add a Coincident constraint to join them.')
    else:
        msg = ('Endpoints touch but are not joined by a Coincident constraint. '
               'They can drift apart when the sketch changes.')
    return Finding(
        check_id=id,
        severity=severity,
        message=msg,
        entities=[a, b],
        viewport_hint={'center': midpoint(wa, wb), 'extent': max(d * 20, 0.1), 'segments': [[wa, wb]] if d else []},
        # a curve's own ends can't be made coincident (an arc closed on itself is a circle): no automatic fix
        fix=None if same_curve else
        lambda: (sketch.geometricConstraints.addCoincident(a, b), 'Joined the endpoints with a Coincident constraint.')[1],
    )
