"""A8: slightly-off right angles.

Pass 1, square grid: when most lines in a sketch sit exactly on one square grid (usually horizontal and
vertical), each line within angle_deg of that grid but not on it is flagged once, touching or not.
Pass 2, corners: lines sharing an endpoint that meet within angle_deg of 90° but not exactly. A line off
square with several neighbors is reported once, as the likely culprit. Lines flagged in pass 1 are skipped.

Not compared yet: lines that are neither near the grid nor touching another line. How to compare those is
an open product question (see CLAUDE.md).
"""
import math
from collections import Counter

from ..base import Finding, midpoint

id = 'A8'
name = 'Slightly-off right angles'
category = 'sketch'
severity = 'warning'
scope = 'sketch'
params = {
    'angle_deg': (0.5, 'Angle tolerance (°)', (0.05, 5.0, 0.05)),
    'grid_mode': ('auto', 'Compare lines to the square grid', [
        ('auto', 'When most lines are square'), ('always', 'Always'), ('never', 'Never (corners only)')]),
}

SQUARE_DEG = 1e-6     # below this a line or corner is exactly square (constrained or drawn exact)
GRID_MAJORITY = 0.5   # auto mode: more than this share of lines must sit exactly on the grid
TOUCH_CM, TOUCH_FRACTION = 0.01, 0.0005  # endpoints this close form a corner: max(0.1 mm, 0.05% of diagonal),
                                         # A9's default gap, so lines that nearly meet still get corner-checked


def detect(ctx):
    eps = ctx.params['angle_deg']
    findings = []
    for sketch in ctx.sketches:
        lines = _lines(sketch)
        dirs = [d for _, d, _ in lines]
        flagged = set()
        grid = square_grid(dirs, ctx.params['grid_mode'], eps)
        if grid is not None:
            # a line exactly on a rotated grid, to constrain against (axis grids use Horizontal/Vertical)
            ref = next((lines[k] for k, d in enumerate(dirs) if grid_deviation(d, grid) <= SQUARE_DEG), None)
            touch = _touch(lines)
            for k, d in enumerate(dirs):
                if lines[k][0].isReference:
                    continue  # projected lines set the grid but can't take a constraint here
                dev = grid_deviation(d, grid)
                if SQUARE_DEG < dev <= eps:
                    flagged.add(k)
                    square_neighbors = [lines[j] for j in _touching(lines, k, touch)
                                        if grid_deviation(dirs[j], grid) <= SQUARE_DEG and not lines[j][0].isReference]
                    findings.append(_grid_finding(ctx, sketch, lines[k], grid, dev, ref, square_neighbors))
        pairs = [(i, j, dev) for i, j, dev in corner_pairs(lines, eps, _touch(lines))
                 if i not in flagged and j not in flagged
                 and not (lines[i][0].isReference and lines[j][0].isReference)]
        for owner, group in group_by_line(pairs).items():
            findings.append(_corner_finding(ctx, sketch, lines, owner, group))
    return findings


def _lines(sketch):
    """[(SketchLine, (dx, dy), ((x0, y0), (x1, y1)))] for non-construction, non-degenerate lines."""
    out = []
    for line in sketch.sketchCurves.sketchLines:
        if line.isConstruction:
            continue
        g = line.geometry
        s, e = (g.startPoint.x, g.startPoint.y), (g.endPoint.x, g.endPoint.y)
        if s != e:
            out.append((line, (e[0] - s[0], e[1] - s[1]), (s, e)))
    return out


def _direction(d):
    return math.degrees(math.atan2(d[1], d[0])) % 180.0


def square_grid(dirs, mode, eps):
    """Grid rotation in degrees [0, 90), or None when the sketch isn't treated as mostly square.
    The grid is the direction more than half the lines share exactly. Without such a majority, 'always'
    falls back to the sketch axes. A majority direction within eps of the axes is a group of tilted lines,
    not a deliberate rotation, so it snaps to the axes and those lines get flagged."""
    if mode == 'never' or not dirs:
        return None
    theta, n = Counter(round(_direction(d) % 90.0, 6) % 90.0 for d in dirs).most_common(1)[0]
    if n <= GRID_MAJORITY * len(dirs):
        return 0.0 if mode == 'always' else None
    return 0.0 if min(theta, 90.0 - theta) <= eps else theta


def grid_deviation(d, theta):
    r = (_direction(d) - theta) % 90.0
    return min(r, 90.0 - r)


def _touch(lines):
    xs = [x for _, _, ends in lines for x, _ in ends]
    ys = [y for _, _, ends in lines for _, y in ends]
    diag = math.hypot(max(xs) - min(xs), max(ys) - min(ys)) if lines else 0.0
    return max(TOUCH_CM, TOUCH_FRACTION * diag)


def corner_pairs(lines, eps, touch):
    """[(i, j, deviation_deg)] for lines with endpoints within touch of each other (shared, constrained,
    or nearly meeting) that are near-square but not square. Grid broadphase with cell size touch."""
    cell = lambda x, y: (math.floor(x / touch), math.floor(y / touch))
    ends = [(k, x, y) for k, (_, _, line_ends) in enumerate(lines) for x, y in line_ends]
    grid = {}
    for end in ends:
        grid.setdefault(cell(end[1], end[2]), []).append(end)
    pairs = {}
    for i, x, y in ends:
        gx, gy = cell(x, y)
        for cx in (gx - 1, gx, gx + 1):
            for cy in (gy - 1, gy, gy + 1):
                for j, ux, uy in grid.get((cx, cy), ()):
                    if i < j and math.hypot(ux - x, uy - y) <= touch:
                        dev = 90.0 - _line_angle(lines[i][1], lines[j][1])
                        if SQUARE_DEG < dev <= eps:
                            pairs[(i, j)] = dev
    return sorted((i, j, dev) for (i, j), dev in pairs.items())


def group_by_line(pairs):
    """Attribute each pair to the line in more near-square pairs (the likely culprit).
    Returns {owner line index, or (i, j) when it's a tie: [pairs]}."""
    count = Counter(k for i, j, _ in pairs for k in (i, j))
    groups = {}
    for i, j, dev in pairs:
        owner = i if count[i] > count[j] else j if count[j] > count[i] else (i, j)
        groups.setdefault(owner, []).append((i, j, dev))
    return groups


def _line_angle(u, v):
    """Angle between two lines (not rays), 0..90°."""
    c = abs(u[0] * v[0] + u[1] * v[1]) / (math.hypot(*u) * math.hypot(*v))
    return math.degrees(math.acos(min(1.0, c)))


def _deg(v, dev):
    """Degrees with enough decimals to show dev: 2 normally, up to 6 so a tiny deviation never reads 0.00°."""
    places = 2 if dev >= 0.01 else min(6, 1 - math.floor(math.log10(dev)))
    return f'{v:.{places}f}°'


def _length(line):
    (x0, y0), (x1, y1) = line[2]
    return math.hypot(x1 - x0, y1 - y0)


def _segment(ctx, sketch, line):
    return [ctx.to_world(sketch, p) for p in (line[0].geometry.startPoint, line[0].geometry.endPoint)]


def _on_first_axis(line, theta):
    r = (_direction(line[1]) - theta) % 180.0
    return min(r, 180.0 - r) <= 45


def _touching(lines, k, touch):
    """Indices of lines with an endpoint within touch of line k's endpoints."""
    return [j for j, other in enumerate(lines) if j != k
            and any(math.dist(p, q) <= touch for p in lines[k][2] for q in other[2])]


def _square_it(gc, line, theta, ref):
    """Add the constraint that puts line on the grid. Returns its name."""
    if theta == 0:
        if _on_first_axis(line, theta):
            gc.addHorizontal(line[0])
            return 'Horizontal'
        gc.addVertical(line[0])
        return 'Vertical'
    if _on_first_axis(line, theta) == _on_first_axis(ref, theta):
        gc.addParallel(line[0], ref[0])
        return 'Parallel'
    gc.addPerpendicular(line[0], ref[0])
    return 'Perpendicular'


def _grid_fix(sketch, line, theta, ref, square_neighbors):
    """Square the line. First lock the touching lines that are already square, so the solver can only
    stretch them along their own direction instead of tilting them (it moves a shared corner)."""
    if theta != 0 and ref is None:
        return None

    def fix():
        gc = sketch.geometricConstraints
        locked = 0
        for n in square_neighbors:
            try:
                _square_it(gc, n, theta, ref)
                locked += 1
            except RuntimeError:
                pass  # already held square some other way (constraint or dimension)
        name = _square_it(gc, line, theta, ref)
        kept = f' Locked {locked} touching square line{"s" if locked != 1 else ""} so they stay square.' if locked else ''
        return f'Added a {name} constraint.{kept}'
    return fix


def _grid_finding(ctx, sketch, line, theta, dev, ref=None, square_neighbors=()):
    first_axis = _on_first_axis(line, theta)
    if theta == 0:
        axis = 'horizontal' if first_axis else 'vertical'
        msg = (f'Line is {_deg(dev, dev)} off {axis}. If it should be {axis}, '
               f'add a {axis.capitalize()} constraint.')
    else:
        msg = (f'Line is {_deg(dev, dev)} off the sketch\'s square grid (rotated {theta:.2f}°). If it should be '
               'square, add a Parallel or Perpendicular constraint to a neighboring line.')
    seg = _segment(ctx, sketch, line)
    return Finding(id, severity, msg, [line[0]],
                   {'center': midpoint(*seg), 'extent': 1.5 * _length(line), 'segments': [seg]},
                   fix=_grid_fix(sketch, line, theta, ref, square_neighbors))


def _culprit_fix(sketch, culprit, neighbors):
    """Make the culprit perpendicular to its neighbors. Left alone, the solver tends to rotate a neighbor
    instead, so one neighbor is held fixed while the constraints go on, then released (nothing moves back:
    the constraints are already satisfied)."""
    def fix():
        gc = sketch.geometricConstraints
        anchor = neighbors[0]
        was_fixed = anchor.isFixed
        anchor.isFixed = True
        try:
            added = 0
            for n in neighbors:
                try:
                    gc.addPerpendicular(culprit, n)
                    added += 1
                except RuntimeError:
                    pass  # redundant: already square to it through the other constraints
            if not added:
                raise RuntimeError('no Perpendicular constraint could be added')
        finally:
            anchor.isFixed = was_fixed
        return f'Made it Perpendicular to {added} neighboring line{"s" if added != 1 else ""}.'
    return fix


def _corner_finding(ctx, sketch, lines, owner, group):
    involved = sorted({k for i, j, _ in group for k in (i, j)})
    segments = [_segment(ctx, sketch, lines[k]) for k in involved]
    extent = 1.5 * max(_length(lines[k]) for k in involved)
    if len(group) == 1 or not isinstance(owner, int):  # tie-owned groups hold one pair; guard anyway
        i, j, dev = group[0]
        # junction: the endpoints the two lines share
        p, q = min(((p, q) for p in segments[0] for q in segments[1]),
                   key=lambda pq: math.dist(pq[0], pq[1]))
        msg = (f'Two lines meet at {_deg(90 - dev, dev)}, off square by {_deg(dev, dev)}. '
               'If they should be square, add a Perpendicular constraint.')
        center = midpoint(p, q)
        a, b = lines[i][0], lines[j][0]
        fix = lambda: (sketch.geometricConstraints.addPerpendicular(a, b), 'Added a Perpendicular constraint.')[1]
    else:
        devs = ', '.join(_deg(dev, dev) for _, _, dev in group)
        msg = (f'This line is off square with {len(group)} touching lines ({devs}). It is probably the one '
               'to fix: add Perpendicular constraints to its neighbors.')
        center = midpoint(*_segment(ctx, sketch, lines[owner]))
        fix = _culprit_fix(sketch, lines[owner][0], [lines[k][0] for k in involved if k != owner])
    return Finding(id, severity, msg, [lines[k][0] for k in involved],
                   {'center': center, 'extent': extent, 'segments': segments}, fix=fix)
