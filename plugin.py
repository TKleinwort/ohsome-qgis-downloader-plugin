import os
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from .ohsome_dialog import OhsomeDialog

class OhsomePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.plugin_dir = os.path.dirname(__file__)
        self.action = None
        self.dlg = None

    def initGui(self):
        icon = QIcon(os.path.join(self.plugin_dir, "img", "icon.png"))
        self.action = QAction(icon, "Ohsome OSM Downloader", self.iface.mainWindow())
        self.action.triggered.connect(self.run)
        self.iface.addToolBarIcon(self.action)
        self.iface.addPluginToMenu("&ohsome", self.action)

    def unload(self):
        self.iface.removePluginMenu("&ohsome", self.action)
        self.iface.removeToolBarIcon(self.action)
        if self.dlg:
            self.dlg.deleteLater()
            self.dlg = None

    def run(self):
        if self.dlg is None:
            self.dlg = OhsomeDialog(self.iface, self.iface.mainWindow())
        self.dlg.show()
        self.dlg.raise_()