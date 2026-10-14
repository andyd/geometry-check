"""Check registration table.

A check is a module exposing:
    id, name, category ('sketch' | 'body'), severity ('error' | 'warning' | 'info'),
    scope ('sketch' | 'body' | 'design'), detect(ctx) -> [Finding]
and optionally params = {key: (default, label[, control])} for user-tunable values (read via ctx.params).
control: (min, max, step) renders a slider; [(value, label), ...] renders a dropdown; omitted is a number box.

To add a check: write the module under checks/<category>/ and append it to CHECKS.
"""
from .sketch import a1_open_profile, a5_tiny_segments, a8_near_orthogonal, a9_hairline_gaps

CHECKS = [a1_open_profile, a5_tiny_segments, a8_near_orthogonal, a9_hairline_gaps]


def by_id(check_id):
    return next(c for c in CHECKS if c.id == check_id)
