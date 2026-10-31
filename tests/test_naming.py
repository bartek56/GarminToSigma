import unittest

from garmin_to_sigma.naming import ActivityFileNamer


class SafeActivityNameTests(unittest.TestCase):
    def setUp(self):
        self.namer = ActivityFileNamer()

    def test_date_name_and_number_order(self):
        self.assertEqual(
            self.namer.make_stem("Morning Ride", "123", "2026-10-17"),
            "2026-10-17_Morning Ride_123",
        )

    def test_windows_unsafe_characters_are_replaced(self):
        self.assertEqual(
            self.namer.make_stem('Ride: <East/West>', "123", "2026-10-17"),
            "2026-10-17_Ride_ _East_West__123",
        )

    def test_empty_name_uses_activity(self):
        self.assertEqual(
            self.namer.make_stem("   ", "123", "2026-10-17"),
            "2026-10-17_activity_123",
        )


if __name__ == "__main__":
    unittest.main()
