import json

from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.core import (
    QgsVectorLayer,
    QgsBlockingNetworkRequest,
    QgsMemoryProviderUtils
)
import os
from qgis.core import QgsVectorLayer

class OhsomeDownloadManager:
    """"""

    OHSOME_BASE_URL = "https://api.heigit.org/ohsome-api/v2-rc"

    EXTRACTION_ENDPOINT = "extraction/features.parquet"

    def __init__(self, base_url: str = OHSOME_BASE_URL):
        self.base_url = base_url
        self._request_counter = 0

    def build_request_body(self, aoi: list[float], ohsome_filter: str, time, clip: bool = True) -> dict:
        """Build the JSON request body for the extraction endpoint call.

        :param aoi: bounding box as [west, south, east, north]
        :param ohsome_filter: raw ohsome filter string
        :param time: either a single ISO8601 string, "latest", or a dict
            with "start"/"end" keys for a time range
        :param clip: whether to clip geometries to the AOI"""

        body = {"aoi": aoi,
                "filter": ohsome_filter,
                "time": time,
                "clip": clip}
        return body

    def fetch_parquet_bytes(self, body: dict, api_key: str | None = None) -> bytes:
        """"""
        url = f"{self.base_url}/{self.EXTRACTION_ENDPOINT}"

        request = QNetworkRequest(QUrl(url))
        request.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json")
        request.setRawHeader(b"accept", b"application/octet-stream")
        if api_key:
            request.setRawHeader(b"authorization", api_key.encode("utf-8"))

        payload = json.dumps(body).encode("utf-8")

        blocking_request = QgsBlockingNetworkRequest()
        error_code = blocking_request.post(request, payload)

        reply = blocking_request.reply()

        if error_code != QgsBlockingNetworkRequest.ErrorCode.NoError:
            content = bytes(reply.content())
            try:
                detail = json.loads(content.decode("utf-8"))
            except (ValueError, UnicodeDecodeError):
                detail = content.decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Request failed ({blocking_request.errorMessage()}): "
                f"{detail}"
            )

        return bytes(reply.content())

    def parquet_bytes_to_layer(self, data: bytes, layer_name: str) -> QgsVectorLayer:
        """Liest die GeoParquet-Antwort aus dem Speicher und gibt sie als
        temporären Memory-Layer (inkl. aller Attribute) zurück."""
        from osgeo import gdal

        if gdal.GetDriverByName("Parquet") is None:
            raise RuntimeError("GDAL's Parquet driver is not available.")

        self._request_counter += 1
        vsi_path = f"/vsimem/ohsome_extraction_{self._request_counter}.parquet"
        gdal.FileFromMemBuffer(vsi_path, data)

        src_layer = None
        try:
            src_layer = QgsVectorLayer(vsi_path, layer_name, "ogr")
            if not src_layer.isValid():
                raise RuntimeError("Could not read GeoParquet response.")

            for f in src_layer.fields():
                print(f.name(), f.typeName(), f.type())
            feat = next(src_layer.getFeatures())
            print(type(feat["tags"]), repr(feat["tags"])[:200])

            mem_layer = QgsMemoryProviderUtils.createMemoryLayer(
                layer_name,
                src_layer.fields(),
                src_layer.wkbType(),
                src_layer.crs(),
            )
            if not mem_layer.isValid():
                raise RuntimeError("Could not create temporary layer.")

            ok, _ = mem_layer.dataProvider().addFeatures(list(src_layer.getFeatures()))
            if not ok:
                raise RuntimeError("Could not copy features to temporary layer.")
            mem_layer.updateExtents()
        finally:
            src_layer = None
            gdal.Unlink(vsi_path)

        return mem_layer