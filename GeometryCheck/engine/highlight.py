"""Viewport feedback for a finding: select its entities, draw an overlay, zoom the camera."""
import adsk.core
import adsk.fusion

_group = None


def clear():
    global _group
    if not (_group and _group.isValid):
        _group = None
        return  # nothing drawn: skip refresh, which pumps the UI event loop (see below)
    _group.deleteMe()
    _group = None
    # refresh() processes pending UI events. Called right after a palette is deleted, a pending timer of
    # that palette fires on a dead object and crashes Fusion (seen 2026-10-13). So only refresh when an
    # overlay was actually erased, and palette.close() clears the overlay before deleting the palette.
    viewport = adsk.core.Application.get().activeViewport
    if viewport:  # None when no document is open
        viewport.refresh()


def locate(finding):
    app = adsk.core.Application.get()
    design = adsk.fusion.Design.cast(app.activeProduct)
    clear()
    _select(app.userInterface, design.rootComponent, finding.entities)
    hint = finding.viewport_hint
    if hint:
        _zoom(app.activeViewport, hint['center'], hint['extent'])
        _draw(design.rootComponent, hint, app.activeViewport.camera)


def _select(ui, root, entities):
    sels = ui.activeSelections
    sels.clear()
    for e in entities:
        comp = e.parentSketch.parentComponent
        if comp != root:
            occs = root.allOccurrencesByComponent(comp)
            if occs.count:
                e = e.createForAssemblyContext(occs.item(0))
        try:
            sels.add(e)
        except RuntimeError:
            pass  # some sketch entities aren't selectable outside sketch edit; the overlay still marks them


def _draw(root, hint, cam):
    global _group
    c, r = hint['center'], hint['extent'] * 0.04
    # depthPriority only orders custom graphics among themselves, so a sketch lying on a body face would
    # z-fight with it. Lift the overlay a hair toward the camera.
    # ponytail: lift is fixed at draw time; orbiting far around can bury it again until the next locate.
    toward = [e - t for e, t in zip(cam.eye.asArray(), cam.target.asArray())]
    norm = sum(v * v for v in toward) ** 0.5 or 1.0
    lift = [v / norm * hint['extent'] * 0.002 for v in toward]
    nudge = lambda p: [a + b for a, b in zip(p, lift)]
    flat = []
    for p, q in hint['segments']:
        flat += nudge(p) + nudge(q)
    # a small cross at the center: the "you are here" mark, visible even when segments are tiny
    for axis in range(3):
        a, b = list(c), list(c)
        a[axis] -= r
        b[axis] += r
        flat += nudge(a) + nudge(b)
    _group = root.customGraphicsGroups.add()
    lines = _group.addLines(adsk.fusion.CustomGraphicsCoordinates.create(flat), [], False, [])
    lines.color = adsk.fusion.CustomGraphicsSolidColorEffect.create(adsk.core.Color.create(230, 40, 40, 255))
    lines.weight = 3
    lines.depthPriority = 1


def _zoom(viewport, center, extent):
    cam = viewport.camera
    dx, dy, dz = center[0] - cam.target.x, center[1] - cam.target.y, center[2] - cam.target.z
    cam.target = adsk.core.Point3D.create(*center)
    cam.eye = adsk.core.Point3D.create(cam.eye.x + dx, cam.eye.y + dy, cam.eye.z + dz)
    cam.viewExtents = extent  # retired but still works on perspective cameras; setExtents doesn't
    cam.isSmoothTransition = True
    viewport.camera = cam
