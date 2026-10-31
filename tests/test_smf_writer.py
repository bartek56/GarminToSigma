import tempfile
import unittest
import datetime
from pathlib import Path

from garmin_to_sigma.models import ActivityMetadata, FitData
from garmin_to_sigma.Sigma.writer import SmfWriter


class SmfWriterTests(unittest.TestCase):
    def test_writes_activity_xml_to_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            fit = FitData(
                start_time=datetime.datetime(2026, 10, 17),
                total_timer_time=100,
                total_distance=1000,
                avg_speed=2,
                max_speed=3,
                total_calories=10,
                total_ascent=5,
                total_descent=4,
                avg_heart_rate=100,
                max_heart_rate=120,
                max_altitude=100,
            )
            metadata = ActivityMetadata(
                file_name="2026-10-17_test_123",
                temperature=20,
                weather=0,
                wind=0,
                weather_description="Sunny",
                wind_speed_mph="",
                trip_profile=0,
                evaluation=3,
                feelings=3,
            )
            path = SmfWriter(directory).write_running(fit, metadata, "123")

            self.assertEqual(
                Path(path), Path(directory) / "2026-10-17_test_123.smf"
            )
            import xml.etree.ElementTree as ET

            parsed = ET.parse(path)
            self.assertEqual(parsed.getroot().tag, "Activity")
            self.assertEqual(parsed.findtext("GeneralInformation/name"), "2026-10-17_test_123")


if __name__ == "__main__":
    unittest.main()
