"""Object-oriented activity and weather analysis."""

import math

from .models import FitData


class WeatherAnalyzer:
    SIGMA_WEATHER_CODES = {
        "sunny": 0,
        "clear": 0,
        "partly_cloudy": 1,
        "light_cloud": 1,
        "cloudy": 2,
        "overcast": 2,
        "light_rain": 3,
        "rain": 4,
        "storm": 5,
        "thunder": 5,
        "snow": 6,
        "fog": 7,
    }

    def __init__(self, weather_data: object):
        self.weather_data = weather_data

    def find_value(self, keys: set[str]):
        return self._find_value(self.weather_data, keys)

    @classmethod
    def _find_value(cls, data: object, keys: set[str]):
        if isinstance(data, dict):
            for key, value in data.items():
                if key.lower() in keys and value is not None:
                    return value
            for value in data.values():
                result = cls._find_value(value, keys)
                if result is not None:
                    return result
        elif isinstance(data, list):
            for value in data:
                result = cls._find_value(value, keys)
                if result is not None:
                    return result
        return None

    @property
    def description(self):
        return self.find_value(
            {
                "desc",
                "weathertypedescription",
                "weatherdescription",
                "weathercondition",
                "conditions",
            }
        )

    @property
    def code(self):
        label = self.find_value(
            {
                "desc",
                "weathertypedescription",
                "weatherdescription",
                "weathercondition",
                "conditions",
                "typekey",
            }
        )
        normalized = str(label or "").lower().replace(" ", "_").replace("-", "_")
        for weather_name, code in self.SIGMA_WEATHER_CODES.items():
            if weather_name in normalized:
                return code
        return ""

    @property
    def temperature_celsius(self):
        value = self.find_value({"temperaturecelsius"})
        if value is not None:
            return float(value)
        fahrenheit = self.find_value({"temperature", "airtemperature", "temp"})
        if fahrenheit is None:
            return None
        return (float(fahrenheit) - 32) * 5 / 9

    @property
    def wind_speed_mph(self):
        return self.find_value({"windspeed"})

    @property
    def wind_speed_mps(self):
        if self.wind_speed_mph is None:
            return None
        return float(self.wind_speed_mph) * 0.44704

    @property
    def beaufort(self):
        speed = self.wind_speed_mps
        if speed is None:
            return ""
        limits = (0.3, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7)
        for code, limit in enumerate(limits):
            if speed < limit:
                return code
        return 12


class ActivityAnalyzer:
    """Calculate Sigma metadata from one typed FIT activity."""

    def __init__(self, fit_data: FitData, activity_type: str):
        self.fit_data = fit_data
        self.activity_type = activity_type

    @property
    def elevation_per_km(self):
        values = (
            self.fit_data.total_distance,
            self.fit_data.total_ascent,
            self.fit_data.total_descent,
        )
        if any(value is None for value in values):
            return 0
        distance, ascent, descent = values
        if not all(math.isfinite(float(value)) for value in values) or distance <= 0:
            return None
        return max(ascent, descent) / (distance / 1000)

    def trip_profile(self) -> int:
        elevation = self.elevation_per_km
        if elevation is None:
            return 0
        if elevation < 15:
            return 0
        if elevation < 30:
            return 1
        if elevation < 50:
            return 2
        if elevation < 80:
            return 3
        return 4

    @staticmethod
    def _score(value: float, thresholds: tuple[float, ...]) -> int:
        for score, threshold in enumerate(thresholds):
            if value < threshold:
                return score
        return len(thresholds)

    def evaluation(self) -> int:
        if self.fit_data.total_distance is None or self.fit_data.avg_speed is None:
            return 0
        distance_km = float(self.fit_data.total_distance) / 1000
        speed_kmh = float(self.fit_data.avg_speed) * 3.6
        if (
            not math.isfinite(distance_km)
            or not math.isfinite(speed_kmh)
            or distance_km <= 0
            or speed_kmh < 0
        ):
            return 0

        if self.activity_type == "running":
            speed_score = self._score(speed_kmh, (6, 8, 10, 12, 14))
            distance_score = self._score(distance_km, (3, 5, 10, 15, 25))
        else:
            speed_score = self._score(speed_kmh, (15, 18, 22, 26, 30))
            distance_score = self._score(distance_km, (10, 25, 50, 80, 120))

        elevation = self.elevation_per_km
        elevation_score = 0 if elevation is None else self._score(
            elevation, (15, 30, 50, 80, 120)
        )
        weighted = 0.5 * speed_score + 0.3 * distance_score + 0.2 * elevation_score
        return min(5, int(weighted + 0.5))
