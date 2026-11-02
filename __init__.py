from .plugin import OhsomePlugin


def classFactory(iface):
    return OhsomePlugin(iface)
