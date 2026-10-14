"""Scan orchestration: run enabled checks, sketch checks first, over the given sketches."""
import hashlib
import json
import os

from ..checks import registry
from ..checks.base import Finding

SETTINGS_PATH = os.path.join(os.path.expanduser('~'), '.geometry-check', 'settings.json')
ATTR_GROUP = 'GeometryCheck'  # ignore marks live as attributes on the entities, inside the design file


class Ctx:
    """What a check sees: the design, the sketches in scope, its params, and unit/space helpers."""

    def __init__(self, design, sketches, settings):
        self.design = design
        self.sketches = sketches
        self.settings = settings
        self.params = {}
        self._occ = {}

    def params_for(self, check_id):
        """Effective params of any check: its defaults overlaid with the user's settings. Lets one check
        reason about another's thresholds (A1 hands borderline points to A9's ACTUAL tolerance, so no
        gap ever falls between the two or gets reported twice)."""
        check = registry.by_id(check_id)
        cfg = self.settings.get(check_id, {})
        return {k: type(spec[0])(cfg.get(k, spec[0])) for k, spec in getattr(check, 'params', {}).items()}

    def check_enabled(self, check_id):
        return self.settings.get(check_id, {}).get('enabled', True)

    def to_world(self, sketch, point):
        """Sketch-space Point3D (cm) -> root-context [x, y, z] (cm)."""
        p = sketch.sketchToModelSpace(point)
        comp = sketch.parentComponent
        if comp.id not in self._occ:
            # ponytail: first occurrence only; a component placed several times highlights at one placement
            occs = self.design.rootComponent.allOccurrencesByComponent(comp)
            self._occ[comp.id] = occs.item(0) if occs.count else None
        if self._occ[comp.id]:
            p.transformBy(self._occ[comp.id].transform2)
        return [p.x, p.y, p.z]

    def fmt_len(self, cm):
        um = self.design.unitsManager
        unit = um.defaultLengthUnits
        return f'{um.convert(cm, "cm", unit):.4g} {unit}'


def all_sketches(design):
    return [sk for comp in design.allComponents for sk in comp.sketches]


def scan(design, settings, sketches=None):
    ctx = Ctx(design, all_sketches(design) if sketches is None else sketches, settings)
    findings = []
    for check in sorted(registry.CHECKS, key=lambda c: c.category != 'sketch'):  # sketch (upstream) first
        if not ctx.check_enabled(check.id):
            continue
        try:  # a bad hand-edited setting fails this check only, like a crash would
            ctx.params = ctx.params_for(check.id)
            findings += check.detect(ctx)
        except Exception as e:  # one broken check must not hide the others' results
            findings.append(Finding(check.id, 'error', f'{check.name} could not run: {e}', [], None))
    for f in findings:
        f.key = _key(f)
        f.ignored = is_ignored(f)
    return findings


def _attr_name(finding):
    return 'ignore_' + finding.check_id


def is_ignored(finding):
    """Ignored = every entity of the finding carries this check's ignore mark. Marks on a subset don't
    count, so overlapping findings that share an entity stay independent."""
    if not finding.entities:
        return False
    try:
        return all(e.attributes.itemByName(ATTR_GROUP, _attr_name(finding)) is not None
                   for e in finding.entities)
    except Exception:
        return False


def mark_intended(finding):
    for e in finding.entities:
        if e.attributes.itemByName(ATTR_GROUP, _attr_name(finding)) is None:
            e.attributes.add(ATTR_GROUP, _attr_name(finding), '1')


def unmark_intended(finding):
    for e in finding.entities:
        attr = e.attributes.itemByName(ATTR_GROUP, _attr_name(finding))
        if attr:
            attr.deleteMe()


def _key(finding):
    """Stable identity: same check on the same entities gives the same key across rescans.
    The basis for ignore lists, cross-links, and the panel addressing findings safely."""
    parts = []
    for e in finding.entities:
        try:
            parts.append(e.entityToken)
        except Exception:
            parts.append(repr(e))
    basis = '|'.join(sorted(parts)) if parts else finding.message
    return finding.check_id + ':' + hashlib.sha1(basis.encode()).hexdigest()[:12]


def load_settings():
    try:
        with open(SETTINGS_PATH) as f:
            settings = json.load(f)
    except FileNotFoundError:
        return {}
    except ValueError:  # corrupt or hand-mangled file: fall back to defaults; next Save rewrites it
        return {}
    return settings if isinstance(settings, dict) else {}


def save_settings(settings):
    os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    tmp = SETTINGS_PATH + '.tmp'
    with open(tmp, 'w') as f:
        json.dump(settings, f, indent=2)
    os.replace(tmp, SETTINGS_PATH)  # atomic: a crash mid-save never leaves a truncated file
