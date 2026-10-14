"""Ribbon commands: Scan, Diagnose Selection, Settings. All open the results palette."""
import os
import traceback

import adsk.core

from . import palette

PANEL_ID = 'InspectPanel'
SCAN, DIAGNOSE, SETTINGS = 'GeometryCheckScan', 'GeometryCheckDiagnose', 'GeometryCheckSettings'
_ICONS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'resources', 'command')
COMMANDS = [
    (SCAN, 'Geometry Check: Scan', 'Scan every sketch for slightly-wrong geometry. Never modifies the design.'),
    (DIAGNOSE, 'Geometry Check: Diagnose Selection', 'Check only the selected sketches or sketch entities.'),
    (SETTINGS, 'Geometry Check: Settings', 'Turn checks on or off and tune their tolerances.'),
]

FIX = palette.FIX_CMD  # hidden (no button): runs one experimental fix as one undoable transaction

_handlers = []
_executing = {}  # cmd_id -> its latest execute handler; replaced per click so clicks don't accumulate


def _ui():
    return adsk.core.Application.get().userInterface


def start():
    ui = _ui()
    panel = ui.allToolbarPanels.itemById(PANEL_ID)
    for cmd_id, name, tip in COMMANDS:
        old = ui.commandDefinitions.itemById(cmd_id)
        if old:
            old.deleteMe()
        cmd_def = ui.commandDefinitions.addButtonDefinition(cmd_id, name, tip, _ICONS)
        handler = _Created(cmd_id)
        cmd_def.commandCreated.add(handler)
        _handlers.append(handler)
        if not panel.controls.itemById(cmd_id):
            panel.controls.addCommand(cmd_def)
    old = ui.commandDefinitions.itemById(FIX)
    if old:
        old.deleteMe()
    fix_def = ui.commandDefinitions.addButtonDefinition(FIX, 'Geometry Check: Apply', 'Apply one fix, ignore, or restore.')
    handler = _Created(FIX)
    fix_def.commandCreated.add(handler)
    _handlers.append(handler)


def stop():
    palette.close()  # first: it must go even if removing a control below fails
    ui = _ui()
    panel = ui.allToolbarPanels.itemById(PANEL_ID)
    for cmd_id in [c[0] for c in COMMANDS] + [FIX]:
        ctrl = panel.controls.itemById(cmd_id) if panel else None
        if ctrl:
            ctrl.deleteMe()
        cmd_def = ui.commandDefinitions.itemById(cmd_id)
        if cmd_def:
            cmd_def.deleteMe()
    _handlers.clear()
    _executing.clear()


class _Created(adsk.core.CommandCreatedEventHandler):
    def __init__(self, cmd_id):
        super().__init__()
        self.cmd_id = cmd_id

    def notify(self, args):
        sels = _ui().activeSelections  # read now: the selection made before clicking the button
        selected = [sels.item(i).entity for i in range(sels.count)]
        handler = _Execute(self.cmd_id, selected)
        args.command.execute.add(handler)
        _executing[self.cmd_id] = handler


class _Execute(adsk.core.CommandEventHandler):
    def __init__(self, cmd_id, selected):
        super().__init__()
        self.cmd_id = cmd_id
        self.selected = selected

    def notify(self, args):
        try:
            if self.cmd_id == SCAN:
                error = palette.run_scan()
                if error:
                    _ui().messageBox(error)
                    return
                palette.show('results')
            elif self.cmd_id == DIAGNOSE:
                self._diagnose()
            elif self.cmd_id == FIX:
                palette.finish_action(args)
            else:
                palette.show('settings')
        except Exception:
            _ui().messageBox('Geometry Check error:\n' + traceback.format_exc())

    def _diagnose(self):
        sketches, only, whole = [], [], []  # whole: sketches picked as a whole (keep all their findings)
        for e in self.selected:
            e = getattr(e, 'nativeObject', None) or e  # proxies in sub-components -> the native entity scans report
            is_sketch = e.objectType == 'adsk::fusion::Sketch'
            sketch = e if is_sketch else getattr(e, 'parentSketch', None)
            if sketch is None:
                continue
            if sketch not in sketches:
                sketches.append(sketch)
            if is_sketch:
                whole.append(e)
            else:
                only.append(e)
                for end in ('startSketchPoint', 'endSketchPoint'):  # a curve's gaps are at its endpoints
                    sp = getattr(e, end, None)
                    if sp:
                        only.append(sp)
        if not sketches:
            _ui().messageBox('Select one or more sketches, or sketch curves/points, then run Diagnose Selection.')
            return
        def keep(f):
            if any(e in only for e in f.entities):
                return True
            sketch = getattr(f.entities[0], 'parentSketch', None) if f.entities else None
            return sketch is not None and sketch in whole

        error = palette.run_scan(sketches, keep)
        if error:
            _ui().messageBox(error)
            return
        palette.show('results')
