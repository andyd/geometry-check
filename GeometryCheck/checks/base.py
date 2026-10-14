from dataclasses import dataclass, field


@dataclass
class Finding:
    check_id: str
    severity: str             # error | warning | info
    message: str              # plain language, shown as-is in the panel
    entities: list            # Fusion entities to highlight (native, not proxies)
    viewport_hint: dict       # {'center': [x,y,z] world cm, 'extent': cm, 'segments': [[p, q], ...]} or None
    linked_findings: list = field(default_factory=list)
    fix: object = None        # optional () -> str: adds constraints to resolve this finding, returns what it did.
                              # Only run by Experimental Fix mode, through engine.fixer (verified, auto-undone).
    key: str = ''             # stable id, set by the scanner: survives rescans (list order doesn't)
    ignored: bool = False     # marked as intentional (attributes on the entities); set by the scanner


def midpoint(p, q):
    return [(a + b) / 2 for a, b in zip(p, q)]
