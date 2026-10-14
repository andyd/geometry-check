import traceback

import adsk.core

from . import commands


def run(_context):
    try:
        commands.start()
    except Exception:
        adsk.core.Application.get().userInterface.messageBox('Geometry Check failed to start:\n' + traceback.format_exc())


def stop(_context):
    try:
        commands.stop()
    except Exception:
        adsk.core.Application.get().userInterface.messageBox('Geometry Check failed to stop:\n' + traceback.format_exc())
