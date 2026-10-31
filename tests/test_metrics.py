import unittest

from garmin_to_sigma.metrics import ActivityAnalyzer, WeatherAnalyzer
from garmin_to_sigma.models import FitData


class MetricsTests(unittest.TestCase):
    def test_trip_profile_thresholds(self):
        self.assertEqual(
            ActivityAnalyzer(FitData(total_distance=10_000, total_ascent=149, total_descent=0), "running").trip_profile(),
            0,
        )
        self.assertEqual(
            ActivityAnalyzer(FitData(total_distance=10_000, total_ascent=150, total_descent=0), "running").trip_profile(),
            1,
        )

    def test_elevation_uses_larger_ascent_or_descent(self):
        self.assertEqual(
            ActivityAnalyzer(FitData(total_distance=20_000, total_ascent=100, total_descent=160), "running").elevation_per_km,
            8,
        )

    def test_evaluation_is_activity_type_aware(self):
        activity = FitData(
            total_distance=10_000,
            avg_speed=3.0,
            total_ascent=100,
            total_descent=100,
        )
        self.assertEqual(ActivityAnalyzer(activity, "running").evaluation(), 2)
        self.assertEqual(ActivityAnalyzer(activity, "cycling").evaluation(), 0)

    def test_weather_and_wind_conversions(self):
        weather = WeatherAnalyzer(
            {"weatherTypeDTO": {"desc": "Mostly Cloudy"}, "temp": 68, "windSpeed": 6}
        )
        self.assertEqual(weather.code, 2)
        self.assertAlmostEqual(weather.temperature_celsius, 20)
        self.assertAlmostEqual(weather.wind_speed_mps, 2.68224)
        self.assertEqual(weather.beaufort, 2)


if __name__ == "__main__":
    unittest.main()
