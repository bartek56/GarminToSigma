"""Typed domain models for Garmin-to-Sigma conversion."""

from dataclasses import dataclass
import datetime


@dataclass
class FitData:
    total_timer_time: float | None = None
    start_time: datetime.datetime | datetime.date | None = None
    total_distance: float | None = None
    avg_speed: float | None = None
    max_speed: float | None = None
    total_calories: float | None = None
    total_ascent: float | None = None
    total_descent: float | None = None
    sport: str | None = None
    avg_heart_rate: float | None = None
    max_heart_rate: float | None = None
    activity_name: str | None = None
    min_altitude: float | None = None
    max_altitude: float | None = None
    avg_temperature: float | None = None
    min_temperature: float | None = None
    max_temperature: float | None = None


@dataclass(frozen=True)
class Activity:
    activity_id: str
    name: str
    activity_type: str
    activity_date: str
    start_time_local: str = ""
    distance: float | None = None
    duration: float | None = None
    elevation_gain: float | None = None
    elevation_loss: float | None = None
    max_elevation: float | None = None
    min_elevation: float | None = None


@dataclass
class ActivityMetadata:
    file_name: str
    temperature: float | str
    weather: int | str
    wind: int | str
    weather_description: str
    wind_speed_mph: float | str
    trip_profile: int
    evaluation: int | str
    feelings: int | str
