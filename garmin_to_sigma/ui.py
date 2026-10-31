"""Console interaction for online and offline conversion."""

import datetime
import math

from .models import Activity, ActivityMetadata, FitData
from .selection import ActivitySelection
from .Utils.helpers import format_duration


class ConsoleUI:
    @staticmethod
    @staticmethod
    def speed_kmh(speed_mps: float) -> float:
        return speed_mps * 3.6

    @staticmethod
    def pace(speed_mps: float):
        if speed_mps <= 0:
            return "Prędkość musi być większa niż 0"
        minutes = 1000 / (speed_mps * 60)
        whole_minutes = int(minutes)
        seconds = int(round((minutes - whole_minutes) * 60))
        return datetime.timedelta(minutes=whole_minutes, seconds=seconds)

    def prompt_start_date(self) -> datetime.date:
        while True:
            value = input("Find activities from date (YYYY-MM-DD): ").strip()
            try:
                return self.parse_date(value)
            except ValueError:
                print("Enter a valid date in YYYY-MM-DD format.")

    @staticmethod
    def parse_date(value: str) -> datetime.date:
        return datetime.date.fromisoformat(value)

    def show_activity_list(self, activities: list[Activity]) -> None:
        print("Cycling and running activities (oldest first):")
        for index, activity in enumerate(activities, start=1):
            distance = (
                "%.2f" % (float(activity.distance) / 1000)
                if activity.distance is not None
                else "N/A"
            )
            duration = (
                format_duration(float(activity.duration))
                if activity.duration is not None
                else "N/A"
            )
            print(
                "%d. %s | %s | %s | %s km | %s"
                % (
                    index,
                    activity.activity_type,
                    activity.name,
                    activity.start_time_local,
                    distance,
                    duration,
                )
            )

    def prompt_activity_selection(self, count: int) -> list[int] | None:
        value = input(
            "Activities to convert [Enter/all=all, e.g. 1,3 or 1-5, q=quit]: "
        ).strip().lower()
        if value == "q":
            return None
        try:
            return ActivitySelection(count).indices(value)
        except ValueError as error:
            print(error)
            return []

    def prompt_single_activity(self, count: int) -> int | None:
        value = input("Activity index to convert (or q to quit): ").strip().lower()
        if value == "q":
            return None
        try:
            indices = ActivitySelection(count).indices(value)
        except ValueError:
            print("Choose one activity index, or q to quit.")
            return -1
        if len(indices) != 1:
            print("Choose one activity index, or q to quit.")
            return -1
        return indices[0]

    def show_fit_data(self, fit: FitData, metadata: ActivityMetadata, activity_type: str, activity_id: str) -> None:
        print("\nData passed to the SMF file:")
        print("activity_type:", activity_type)
        print("activity_id:", activity_id)
        print("FIT activity data:")
        for name, value in fit.__dict__.items():
            if value is None:
                continue
            if name == "total_timer_time":
                print(name, value, "s   ", format_duration(value))
            elif name == "total_distance":
                print(name, value, "m")
            elif name in {"avg_temperature", "min_temperature", "max_temperature"}:
                print(name, value, "°C")
            elif name in {"avg_speed", "max_speed"}:
                print(
                    name,
                    value,
                    "m/s",
                    self.speed_kmh(value),
                    "km/h",
                    str(self.pace(value)),
                    "/km",
                )
            else:
                print(name, value)
        print("SMF metadata:")
        for key, value in metadata.__dict__.items():
            if key == "temperature":
                if value in (None, ""):
                    print("temperature: unavailable")
                else:
                    print("temperature: %.1f °C" % value)
            elif key == "weather":
                print("weather: %s (%s)" % (value, metadata.weather_description or "unknown"))
            elif key == "wind":
                if metadata.wind_speed_mph in (None, ""):
                    print("wind: %s Beaufort" % value)
                else:
                    print(
                        "wind: %s Beaufort (Garmin: %s mph / %.1f m/s)"
                        % (value, metadata.wind_speed_mph, float(metadata.wind_speed_mph) * 0.44704)
                    )
            elif key not in {"weather_description", "wind_speed_mph"}:
                print("%s: %s" % (key, value))

    @staticmethod
    def prompt_temperature() -> float:
        while True:
            value = input("Temperature [°C]: ").strip().replace(",", ".")
            try:
                temperature = float(value)
            except ValueError:
                print("Enter a numeric temperature in °C.")
                continue
            if not math.isfinite(temperature):
                print("Enter a finite temperature in °C.")
                continue
            return temperature

    @staticmethod
    def prompt_manual_ratings() -> tuple[str, str]:
        feelings = input("Feelings [0-4]: ").strip()
        evaluation = input("Evaluation [0-5]: ").strip()
        return feelings, evaluation
