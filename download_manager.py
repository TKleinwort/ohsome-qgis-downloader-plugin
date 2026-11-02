import json

from qgis.PyQt.QtCore import QUrl
from qgis.PyQt.QtNetwork import QNetworkRequest
from qgis.core import QgsVectorLayer, QgsBlockingNetworkRequest


class OhsomeDownloadManager:
    """Handles building requests to the ohsome API extraction endpoint
    and converting GeoParquet responses into QGIS vector layers using
    GDAL's OGR Parquet driver"""

    OHSOME_BASE_URL = "https://api.heigit.org/ohsome-api/v2-rc"

    EXTRACTION_ENDPOINT = "extraction/features.parquet"

    def __init__(self, base_url: str = OHSOME_BASE_URL):
        self.base_url = base_url
        self._request_counter = 0

    def build_request_body(
        self, aoi: list[float], ohsome_filter: str, time, clip: bool = True
    ) -> dict:
        """Build the JSON request body for the extraction endpoint call.

        :param aoi: bounding box as [west, south, east, north]
        :param ohsome_filter: raw ohsome filter string
        :param time: either a single str "latest" or a dict with "start"/"end" keys for a time range
        :param clip: whether to clip geometries to the AOI"""

        body = {"aoi": aoi, "filter": ohsome_filter, "time": time, "clip": clip}
        return body

    def fetch_parquet_bytes(self, body: dict, api_key: str | None = None) -> bytes:
        """Call the ohsome extraction endpoint and return the raw
        GeoParquet response bytes"""
        url = f"{self.base_url}/{self.EXTRACTION_ENDPOINT}"

        request = QNetworkRequest(QUrl(url))
        request.setHeader(
            QNetworkRequest.KnownHeaders.ContentTypeHeader, "application/json"
        )
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
                f"Request failed ({blocking_request.errorMessage()}): {detail}"
            )

        return bytes(reply.content())

    def parquet_bytes_to_layer(self, data: bytes, layer_name: str) -> QgsVectorLayer:
        """Load GeoParquet bytes into an OGR-backed QgsVectorLayer via /vsimem/."""
        from osgeo import gdal

        if gdal.GetDriverByName("Parquet") is None:
            raise RuntimeError("GDAL's Parquet driver is not available.")

        self._request_counter += 1
        vsi_path = f"/vsimem/ohsome_extraction_{self._request_counter}.parquet"
        gdal.FileFromMemBuffer(vsi_path, data)

        layer = QgsVectorLayer(vsi_path, layer_name, "ogr")
        if not layer.isValid():
            gdal.Unlink(vsi_path)
            raise RuntimeError("Could not read GeoParquet response.")

        layer.willBeDeleted.connect(lambda p=vsi_path: gdal.Unlink(p))
        return layer
