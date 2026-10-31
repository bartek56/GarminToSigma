"""Garmin FIT activity parsing."""

import math

import fitdecode

from ..models import FitData


class FitParser:
    def parse(self, filename: str) -> FitData:
        print("Reading fit file ...")
        fit_data = FitData()
        minimum_altitudes = []
        maximum_altitudes = []
        record_altitudes = []
        fit_temperatures = []
        minimum_temperatures = []
        maximum_temperatures = []
        fit_average_temperature = None

        with fitdecode.FitReader(filename) as fit:
            for frame in fit:
                if not isinstance(frame, fitdecode.FitDataMessage):
                    continue
                record_altitude = None
                for field in frame.fields:
                    field_name = field.name.lower()
                    field_value = field.value
                    if field_value is not None:
                        try:
                            numeric_value = float(field_value)
                        except (TypeError, ValueError):
                            numeric_value = None
                        if numeric_value is not None and math.isfinite(numeric_value):
                            if "min_altitude" in field_name:
                                minimum_altitudes.append(numeric_value)
                            elif "max_altitude" in field_name:
                                maximum_altitudes.append(numeric_value)
                            elif frame.name == "record" and field_name in {
                                "altitude",
                                "enhanced_altitude",
                            }:
                                if field_name == "enhanced_altitude" or record_altitude is None:
                                    record_altitude = numeric_value

                    if frame.name == "session" and field_name == "avg_heart_rate":
                        if field_value is not None:
                            fit_data.avg_heart_rate = field_value
                    if frame.name == "session" and field_name == "max_heart_rate":
                        if field_value is not None:
                            fit_data.max_heart_rate = field_value
                    if frame.name == "session" and field_name == "total_timer_time":
                        if field_value is not None:
                            fit_data.total_timer_time = field_value
                    if frame.name == "session" and field_name == "total_ascent":
                        if field_value is not None:
                            fit_data.total_ascent = field_value
                    if frame.name == "session" and field_name == "total_descent":
                        if field_value is not None:
                            fit_data.total_descent = field_value
                    if frame.name == "session" and field_name in {"max_speed", "enhanced_max_speed"}:
                        if field_value is not None:
                            if field_name == "enhanced_max_speed" or fit_data.max_speed is None:
                                fit_data.max_speed = field_value
                    if frame.name == "session" and field_name in {"avg_speed", "enhanced_avg_speed"}:
                        if field_value is not None:
                            if field_name == "enhanced_avg_speed" or fit_data.avg_speed is None:
                                fit_data.avg_speed = field_value
                    if frame.name == "session" and field_name == "total_calories":
                        if field_value is not None:
                            fit_data.total_calories = field_value
                    if field_name == "start_time" and field_value is not None:
                        fit_data.start_time = field_value
                    if field_name == "sport" and field_value is not None:
                        fit_data.sport = field_value
                    if field_name in {"name", "activity_name"} and field_value:
                        fit_data.activity_name = str(field_value)
                    if frame.name == "session" and field_name == "total_distance":
                        if field_value is not None:
                            fit_data.total_distance = field_value
                    if "temperature" in field_name and field_value is not None:
                        try:
                            temperature = float(field_value)
                        except (TypeError, ValueError):
                            continue
                        if not math.isfinite(temperature):
                            continue
                        if field_name == "avg_temperature":
                            fit_average_temperature = temperature
                        elif field_name == "min_temperature":
                            minimum_temperatures.append(temperature)
                        elif field_name == "max_temperature":
                            maximum_temperatures.append(temperature)
                        elif frame.name == "record" and field_name == "temperature":
                            fit_temperatures.append(temperature)
                if frame.name == "record" and record_altitude is not None:
                    record_altitudes.append(record_altitude)

        fit_data.min_altitude = min(minimum_altitudes or record_altitudes) if (minimum_altitudes or record_altitudes) else None
        fit_data.max_altitude = max(maximum_altitudes or record_altitudes) if (maximum_altitudes or record_altitudes) else None
        if fit_data.min_altitude is None or fit_data.max_altitude is None:
            raise ValueError("The FIT file does not contain usable altitude data.")

        if fit_average_temperature is not None:
            fit_data.avg_temperature = fit_average_temperature
        elif fit_temperatures:
            fit_data.avg_temperature = sum(fit_temperatures) / len(fit_temperatures)
        if minimum_temperatures:
            fit_data.min_temperature = min(minimum_temperatures)
        elif fit_temperatures:
            fit_data.min_temperature = min(fit_temperatures)
        if maximum_temperatures:
            fit_data.max_temperature = max(maximum_temperatures)
        elif fit_temperatures:
            fit_data.max_temperature = max(fit_temperatures)
        return fit_data
