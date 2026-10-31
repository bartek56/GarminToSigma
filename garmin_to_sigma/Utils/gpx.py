"""Create a GPX track from FIT record messages."""

import datetime
import math
import xml.etree.ElementTree as ET

import fitdecode


class FitGpxWriter:
    """Write the GPS track contained in a FIT file as a GPX 1.1 file."""

    def write(self, fit_path: str, gpx_path: str, track_name: str) -> None:
        points: list[dict[str, object]] = []
        with fitdecode.FitReader(fit_path) as fit:
            for frame in fit:
                if not isinstance(frame, fitdecode.FitDataMessage) or frame.name != "record":
                    continue
                values = {field.name.lower(): field.value for field in frame.fields}
                latitude = self._coordinate(values.get("position_lat"))
                longitude = self._coordinate(values.get("position_long"))
                if latitude is None or longitude is None:
                    continue
                altitude = values.get("enhanced_altitude", values.get("altitude"))
                timestamp = values.get("timestamp")
                points.append(
                    {
                        "latitude": latitude,
                        "longitude": longitude,
                        "altitude": self._number(altitude),
                        "timestamp": timestamp,
                    }
                )
        if not points:
            raise ValueError("The FIT file does not contain GPS records for GPX export.")

        root = ET.Element(
            "gpx",
            {
                "version": "1.1",
                "creator": "GarminToSigma",
                "xmlns": "http://www.topografix.com/GPX/1/1",
            },
        )
        track = ET.SubElement(root, "trk")
        ET.SubElement(track, "name").text = track_name
        segment = ET.SubElement(track, "trkseg")
        for point in points:
            track_point = ET.SubElement(
                segment,
                "trkpt",
                {
                    "lat": "%.8f" % point["latitude"],
                    "lon": "%.8f" % point["longitude"],
                },
            )
            if point["altitude"] is not None:
                ET.SubElement(track_point, "ele").text = "%.3f" % point["altitude"]
            timestamp = self._timestamp(point["timestamp"])
            if timestamp:
                ET.SubElement(track_point, "time").text = timestamp

        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")
        tree.write(gpx_path, encoding="utf-8", xml_declaration=True)

    @staticmethod
    def _number(value: object) -> float | None:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    @classmethod
    def _coordinate(cls, value: object) -> float | None:
        number = cls._number(value)
        if number is None:
            return None
        # FIT position fields are usually semicircles. fitdecode versions that
        # expose degrees already produce values in the valid latitude/longitude
        # range, so do not convert those again.
        if abs(number) > 180:
            number = number * 180 / 2**31
        return number if -180 <= number <= 180 else None

    @staticmethod
    def _timestamp(value: object) -> str | None:
        if not isinstance(value, (datetime.datetime, datetime.date)):
            return None
        if isinstance(value, datetime.date) and not isinstance(value, datetime.datetime):
            value = datetime.datetime.combine(value, datetime.time())
        if value.tzinfo is None:
            value = value.replace(tzinfo=datetime.timezone.utc)
        return value.astimezone(datetime.timezone.utc).isoformat().replace("+00:00", "Z")
