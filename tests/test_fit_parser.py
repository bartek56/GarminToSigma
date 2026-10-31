import datetime
import unittest
from dataclasses import dataclass
from unittest.mock import patch

import fitdecode

from garmin_to_sigma.Garmin.fit_parser import FitParser
from garmin_to_sigma.models import FitData


@dataclass
class FakeField:
    name: str
    value: object


class FakeFrame:
    def __init__(self, name, fields):
        self.name = name
        self.fields = [FakeField(*field) for field in fields]


class FakeReader:
    def __init__(self, frames):
        self.frames = frames

    def __enter__(self):
        return iter(self.frames)

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class FitParserTests(unittest.TestCase):
    def test_session_totals_are_not_overwritten_by_split_summaries(self):
        frames = [
            FakeFrame(
                "session",
                [
                    ("start_time", datetime.datetime(2026, 8, 2)),
                    ("total_timer_time", 4271.647),
                    ("total_distance", 10877.64),
                    ("total_calories", 713),
                    ("total_ascent", 89),
                    ("total_descent", 82),
                    ("avg_speed", 2.546),
                    ("sport", "running"),
                ],
            ),
            FakeFrame(
                "split_summary",
                [
                    ("total_timer_time", 261.194),
                    ("total_distance", 340.9),
                    ("total_calories", 22),
                ],
            ),
            FakeFrame("record", [("altitude", 100)]),
            FakeFrame("record", [("altitude", 110)]),
        ]

        with patch.object(fitdecode, "FitDataMessage", FakeFrame), patch(
            "garmin_to_sigma.Garmin.fit_parser.fitdecode.FitReader",
            return_value=FakeReader(frames),
        ):
            result = FitParser().parse("activity.fit")

        self.assertIsInstance(result, FitData)
        self.assertEqual(result.total_distance, 10877.64)
        self.assertEqual(result.total_calories, 713)
        self.assertEqual(result.total_distance, 10877.64)
        self.assertEqual(result.total_timer_time, 4271.647)
        self.assertEqual(result.total_calories, 713)
        self.assertEqual(result.total_ascent, 89)
        self.assertEqual(result.total_descent, 82)
        self.assertEqual(result.min_altitude, 100)
        self.assertEqual(result.max_altitude, 110)


if __name__ == "__main__":
    unittest.main()
