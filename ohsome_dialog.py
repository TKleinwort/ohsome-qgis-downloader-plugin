import os
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QDialog
from qgis.PyQt.QtGui import QPixmap
from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform,
    QgsProject, QgsSettings,
)
from .download_manager import OhsomeDownloadManager

FORM_CLASS, _ = uic.loadUiType(
    os.path.join(os.path.dirname(__file__), "ohsome_dialog.ui")
)

TOPICS = {
    "Gebäude": "building=* and building!=no and geometry:polygon",
}


class OhsomeDialog(QDialog, FORM_CLASS):
    def __init__(self, iface, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.iface = iface
        self.manager = OhsomeDownloadManager()

        logo = os.path.join(os.path.dirname(__file__), "img", "ohsome-logo.svg")
        self.labelLogo.setPixmap(QPixmap(logo).scaledToHeight(48))

        self.comboTopic.clear()
        self.comboTopic.addItems(TOPICS.keys())

        self.extentGroupBox.setMapCanvas(iface.mapCanvas())
        self.extentGroupBox.setOutputCrs(QgsCoordinateReferenceSystem("EPSG:4326"))

        self.lineEditApiKey.setText(QgsSettings().value("ohsome/api_key", ""))

        self.pushButtonDownload.clicked.connect(self.on_download)
        self.pushButtonClose.clicked.connect(self.close)

    def get_aoi(self) -> list[float]:
        rect = self.extentGroupBox.outputExtent()
        crs = self.extentGroupBox.outputCrs()
        wgs84 = QgsCoordinateReferenceSystem("EPSG:4326")
        if crs != wgs84:
            tr = QgsCoordinateTransform(crs, wgs84, QgsProject.instance())
            rect = tr.transformBoundingBox(rect)
        return [rect.xMinimum(), rect.yMinimum(), rect.xMaximum(), rect.yMaximum()]

    def on_download(self):
        api_key = self.lineEditApiKey.text().strip() or None
        QgsSettings().setValue("ohsome/api_key", api_key or "")
        try:
            body = self.manager.build_request_body(
                aoi=self.get_aoi(),
                ohsome_filter=TOPICS[self.comboTopic.currentText()],
                time=self.lineEditTime.text().strip() or "latest",
                clip=self.checkBoxClip.isChecked(),
            )
            data = self.manager.fetch_parquet_bytes(body, api_key=api_key)
            layer = self.manager.parquet_bytes_to_layer(data, "ohsome_buildings")
            QgsProject.instance().addMapLayer(layer)
            self.iface.messageBar().pushSuccess("ohsome", f"{layer.featureCount()} Features geladen")
        except Exception as exc:
            self.iface.messageBar().pushCritical("ohsome", str(exc))