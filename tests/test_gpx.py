import datetime
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

import fitdecode

from garmin_to_sigma.Utils.gpx import FitGpxWriter


class FakeField:
    def __init__(self, name, value):
        self.name = name
        self.value = value


class FakeFrame:
    def __init__(self, name, fields):
        self.name = name
        self.fields = [FakeField(name, value) for name, value in fields]


class FakeReader:
    def __init__(self, frames):
        self.frames = frames

    def __enter__(self):
        return iter(self.frames)

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class FitGpxWriterTests(unittest.TestCase):
    def test_writes_gpx_from_fit_gps_records(self):
        frames = [
            FakeFrame(
                "record",
                [
                    ("position_lat", 52.1),
                    ("position_long", 21.0),
                    ("altitude", 100),
                    ("timestamp", datetime.datetime(2026, 10, 1, 8, 0)),
                ],
            )
        ]
        with tempfile.TemporaryDirectory() as directory:
            output = "%s/activity.gpx" % directory
            with patch.object(fitdecode, "FitDataMessage", FakeFrame), patch(
                "garmin_to_sigma.Utils.gpx.fitdecode.FitReader",
                return_value=FakeReader(frames),
            ):
                FitGpxWriter().write("activity.fit", output, "Morning ride")

            root = ET.parse(output).getroot()
            point = root.find("{http://www.topografix.com/GPX/1/1}trk/{http://www.topografix.com/GPX/1/1}trkseg/{http://www.topografix.com/GPX/1/1}trkpt")
            self.assertEqual(point.attrib["lat"], "52.10000000")
            self.assertEqual(point.attrib["lon"], "21.00000000")


if __name__ == "__main__":
    unittest.main()
