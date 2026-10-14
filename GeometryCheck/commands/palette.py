"""Results palette: holds the last scan, talks to ui/palette.html."""
import json
import os
import platform
import traceback
import webbrowser
from urllib.parse import urlencode

import adsk.core
import adsk.fusion

from ..checks import registry
from ..engine import fixer, highlight, scanner

PALETTE_ID = 'GeometryCheckPalette'
ADDIN_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML = os.path.join(ADDIN_DIR, 'ui', 'palette.html')
with open(os.path.join(ADDIN_DIR, 'GeometryCheck.manifest')) as _f:
    VERSION = json.load(_f)['version']  # read at load: the panel shows the version actually running
STAGE = 'alpha'
FIX_CMD = 'GeometryCheckApplyFix'  # hidden command: fix/ignore/restore each run as one undoable transaction
FEEDBACK_URL = 'https://tally.so/r/eq1VVE'  # anonymous form; 'version' arrives as a hidden field
ISSUES_URL = 'https://github.com/andyd/geometry-check/issues/new'

_handlers = []
_findings = []
_design = None  # the design _findings came from
_scanned = None  # number of sketches in the last scan; None = not scanned yet
_view = 'results'
_settings = None
_scope = (None, None)  # (sketches, keep) of the last scan, re-run after a fix
_pending = None        # (kind, key) the Fix command will run: kind is 'fix' | 'ignore' | 'restore'
_notice = None         # one-shot success message for the panel


def settings():
    global _settings
    if _settings is None:
        _settings = scanner.load_settings()
    return _settings


NO_DESIGN = 'Geometry Check works in the Design workspace. Switch to a design, then Scan.'


def run_scan(sketches=None, keep=None):
    """Scan and cache. keep(finding) -> bool narrows results (Diagnose Selection).
    Returns an error message, or None. Never reports 'no issues' when nothing was scanned."""
    global _findings, _scanned, _design, _scope
    highlight.clear()
    design = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
    if not design:
        return NO_DESIGN  # drawing, CAM, or no document: keep the last results rather than a false all-clear
    if sketches is None:
        sketches = scanner.all_sketches(design)
    found = scanner.scan(design, settings(), sketches)
    _findings = [f for f in found if keep(f)] if keep else found
    _scanned, _design, _scope = len(sketches), design, (sketches, keep)
    return None


def experimental():
    return settings().get('mode') == 'experimental'


def _by_key(key):
    """Index of the finding with this key, or None. Keys survive rescans; list positions don't."""
    return next((i for i, f in enumerate(_findings) if f.key == key), None)


def _request_action(kind, key):
    """From the panel: validate, then run the hidden command, which applies the action in a transaction."""
    global _pending
    idx = _by_key(key)
    problem = _check_current(idx)
    if problem:
        return problem
    if kind == 'fix':
        if not experimental():
            return {'error': 'Fixes are off. Turn on Experimental fixes in Settings to use them.'}
        if not _findings[idx].fix:
            return {'error': 'There is no automatic fix for this finding yet.'}
        if _findings[idx].ignored:
            return {'error': 'This finding is ignored. Restore it before fixing it.'}
    highlight.clear()  # now, not inside the command: clear() may refresh the viewport
    _pending = (kind, key)
    adsk.core.Application.get().userInterface.commandDefinitions.itemById(FIX_CMD).execute()
    return {'ok': True}


def finish_action(args):
    """Hidden command's execute handler: apply fix/ignore/restore, keep or abort the transaction."""
    global _pending, _notice
    (kind, key), _pending = _pending or (None, None), None
    idx = _by_key(key) if key else None
    if idx is None:
        return
    finding = _findings[idx]
    try:
        if kind == 'fix':
            ok, message = fixer.apply_and_verify(_design, finding, settings())
            message = 'Fixed: ' + message + ' Ctrl+Z undoes it.' if ok else message
        elif kind == 'ignore':
            scanner.mark_intended(finding)
            ok, message = True, ('Ignored: this finding is marked as intentional and hidden from future '
                                 'scans. The mark is saved in the design. Restore it under "show ignored".')
        else:
            scanner.unmark_intended(finding)
            ok, message = True, 'Restored: this finding will show up in scans again.'
    except Exception:  # anything unexpected: roll back rather than leave a half-applied change
        ok, message = False, ('Undone: hit an unexpected error. '
                              + traceback.format_exc().strip().splitlines()[-1])
    if ok:
        run_scan(*_scope)
        _notice = message
        _push()
    else:
        args.executeFailed = True  # aborts the command's transaction: the design is left as it was
        _push(error=message)


def _push(error=None):
    pal = adsk.core.Application.get().userInterface.palettes.itemById(PALETTE_ID)
    if pal:
        pal.sendInfoToHTML('state', json.dumps(dict(_state(), error=error) if error else _state()))


def _feedback(kind):
    os_name = {'Darwin': 'macOS', 'Windows': 'Windows'}.get(platform.system(), platform.system())
    if kind == 'github':
        url = ISSUES_URL + '?' + urlencode({'template': 'bug_report.yml', 'version': VERSION, 'os': os_name})
    else:
        url = FEEDBACK_URL + '?' + urlencode({'version': VERSION, 'os': os_name})
    webbrowser.open(url)
    return {'ok': True}


def show(view='results'):
    global _view
    _view = view
    ui = adsk.core.Application.get().userInterface
    pal = ui.palettes.itemById(PALETTE_ID)
    if pal:
        pal.isVisible = True
        pal.sendInfoToHTML('state', json.dumps(_state()))
        return  # a freshly added palette pulls its state on load ('ready') instead
    pal = ui.palettes.add(PALETTE_ID, 'Geometry Check', HTML, True, True, True, 360, 640, True)
    pal.dockingState = adsk.core.PaletteDockingStates.PaletteDockStateRight
    for event, handler in ((pal.incomingFromHTML, _HTMLHandler()), (pal.closed, _ClosedHandler())):
        event.add(handler)
        _handlers.append(handler)


def close():
    highlight.clear()  # before deleting the palette: see highlight.clear
    pal = adsk.core.Application.get().userInterface.palettes.itemById(PALETTE_ID)
    if pal:
        pal.deleteMe()
    _handlers.clear()


def _state():
    global _notice
    cfg = settings()
    notice, _notice = _notice, None
    return {
        'version': VERSION,
        'stage': STAGE,
        'mode': cfg.get('mode', 'detect'),
        'notice': notice,
        'view': _view,
        'scanned': _scanned,
        'checks': [{
            'id': c.id, 'name': c.name, 'category': c.category, 'severity': c.severity,
            'enabled': cfg.get(c.id, {}).get('enabled', True),
            'params': [{'key': k, 'label': spec[1], 'value': cfg.get(c.id, {}).get(k, spec[0]),
                        'control': spec[2] if len(spec) > 2 else None}
                       for k, spec in getattr(c, 'params', {}).items()],
        } for c in registry.CHECKS],
        'findings': [{
            'key': f.key, 'check_id': f.check_id, 'severity': f.severity, 'message': f.message,
            'where': _where(f), 'locatable': bool(f.viewport_hint), 'fixable': f.fix is not None,
            'ignored': f.ignored,
        } for f in _findings],
    }


def _where(finding):
    try:
        return finding.entities[0].parentSketch.name
    except (IndexError, AttributeError, RuntimeError):
        return ''


def _check_current(idx):
    """None if finding idx still belongs to the active design, else an error reply."""
    if idx is None:
        return {'error': 'This finding is out of date. Scan again.'}
    active = adsk.fusion.Design.cast(adsk.core.Application.get().activeProduct)
    if not active:
        return {'error': 'Switch to the Design workspace first.'}
    if not _design or not _design.isValid or active != _design:
        return {'error': 'These results are for a different document. Switch back to it, or Scan this one.'}
    if not all(e.isValid for e in _findings[idx].entities):
        return {'error': 'This finding is out of date; the design changed. Scan again.'}
    return None


def _locate(key):
    idx = _by_key(key)
    problem = _check_current(idx)
    if problem:
        return problem
    highlight.locate(_findings[idx])
    return {'ok': True}


def _save_settings(new):
    global _settings
    _settings = new
    scanner.save_settings(new)


class _HTMLHandler(adsk.core.HTMLEventHandler):
    def notify(self, args):
        args = adsk.core.HTMLEventArgs.cast(args)
        try:
            data = json.loads(args.data) if args.data else {}
            if args.action == 'locate':
                reply = _locate(data['key'])
            elif args.action in ('fix', 'ignore', 'restore'):
                reply = _request_action(args.action, data['key'])
            elif args.action == 'feedback':
                reply = _feedback(data.get('kind'))
            else:
                error = None
                if args.action == 'scan':
                    error = run_scan()
                elif args.action == 'save_settings':
                    _save_settings(data['settings'])
                reply = dict(_state(), error=error) if error else _state()
            args.returnData = json.dumps(reply)
        except Exception:
            args.returnData = json.dumps({'error': traceback.format_exc()})


class _ClosedHandler(adsk.core.UserInterfaceGeneralEventHandler):
    def notify(self, args):
        highlight.clear()
