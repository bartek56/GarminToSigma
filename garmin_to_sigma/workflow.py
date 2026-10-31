"""Online and offline conversion workflows."""

import datetime
import math
import os
import re
from dataclasses import replace

from .Garmin.fit_parser import FitParser
from .metrics import ActivityAnalyzer, WeatherAnalyzer
from .models import Activity, ActivityMetadata, FitData
from .naming import ActivityFileNamer
from .Sigma.writer import SmfWriter
from .source import ActivitySource
from .ui import ConsoleUI


class ConversionWorkflow:
    def __init__(
        self,
        client: ActivitySource | None,
        output_dir: str,
        ui: ConsoleUI | None = None,
    ):
        self.client = client
        self.output_dir = output_dir
        self.ui = ui or ConsoleUI()
        self.namer = ActivityFileNamer()
        self.fit_parser = FitParser()
        self.writer = SmfWriter(output_dir)

    def run_online(
        self, automatic: bool, start_date: datetime.date | None = None
    ) -> None:
        if self.client is None:
            raise ValueError("Online workflow requires an activity source client.")
        self.client.login()
        activities = self.client.list_activities(start_date or self.ui.prompt_start_date())
        if not activities:
            print("No uncached cycling or running activities found from that date.")
            return

        while activities:
            self.ui.show_activity_list(activities)
            if automatic:
                indices = self.ui.prompt_activity_selection(len(activities))
                if indices is None:
                    return
                if not indices:
                    continue
                for index in indices:
                    self.convert_online_activity(activities[index], automatic=True)
                return

            index = self.ui.prompt_single_activity(len(activities))
            if index is None:
                return
            if index < 0:
                continue
            activity = activities.pop(index)
            self.convert_online_activity(activity, automatic=False)
        print("No more uncached activities from that date.")

    def convert_online_activity(self, activity: Activity, automatic: bool) -> None:
        details = self.client.get_details(activity.activity_id)
        activity = self.client.enrich_activity(activity, details)
        weather = self.client.get_weather(activity.activity_id)
        fit_path = self.client.download_fit(activity)
        fit = self.fit_parser.parse(fit_path)
        fit = self._apply_activity_stats(fit, activity)
        self.client.download_gpx(activity)
        self._convert(activity, fit, weather, automatic, gpx_available=True)

    def convert_offline(self, fit_path: str, automatic: bool) -> None:
        fit = self.fit_parser.parse(fit_path)
        activity = self._offline_activity(fit_path, fit)
        self._convert(activity, fit, {}, automatic, gpx_available=False)

    def _convert(
        self,
        activity: Activity,
        fit: FitData,
        weather_data: object,
        automatic: bool,
        gpx_available: bool,
    ) -> None:
        metadata = self._metadata(activity, fit, weather_data, automatic)
        self.ui.show_fit_data(fit, metadata, activity.activity_type, activity.activity_id)
        if metadata.temperature == "":
            metadata.temperature = self.ui.prompt_temperature()
        if not automatic:
            metadata.feelings, metadata.evaluation = self.ui.prompt_manual_ratings()
        if activity.activity_type == "running":
            self.writer.write_running(fit, metadata, activity.activity_id)
        else:
            self.writer.write_cycling(fit, metadata, activity.activity_id)

    def _metadata(
        self,
        activity: Activity,
        fit: FitData,
        weather_data: object,
        automatic: bool,
    ) -> ActivityMetadata:
        weather = WeatherAnalyzer(weather_data)
        temperature = fit.avg_temperature
        if temperature is None:
            temperature = weather.temperature_celsius
        if temperature is None:
            temperature = ""
        analyzer = ActivityAnalyzer(fit, activity.activity_type)
        return ActivityMetadata(
            file_name=self.namer.make_stem(
                activity.name, activity.activity_id, activity.activity_date
            ),
            temperature=temperature,
            weather=weather.code,
            wind=weather.beaufort,
            weather_description=weather.description or "",
            wind_speed_mph=weather.wind_speed_mph if weather.wind_speed_mph is not None else "",
            trip_profile=analyzer.trip_profile(),
            evaluation=analyzer.evaluation() if automatic else "",
            feelings=3 if automatic else "",
        )

    @staticmethod
    def _apply_activity_stats(fit: FitData, activity: Activity) -> FitData:
        values = (
            ("max_altitude", activity.max_elevation, "maxElevation"),
            ("min_altitude", activity.min_elevation, "minElevation"),
            ("total_ascent", activity.elevation_gain, "elevationGain"),
            ("total_descent", activity.elevation_loss, "elevationLoss"),
        )
        for field_name, value, garmin_field in values:
            if value is not None:
                try:
                    numeric = float(value)
                except (TypeError, ValueError) as error:
                    raise ValueError(
                        "Activity source returned an invalid %s value." % garmin_field
                    ) from error
                if not math.isfinite(numeric):
                    raise ValueError(
                        "Activity source returned a non-finite %s value." % garmin_field
                    )
                fit = replace(fit, **{field_name: numeric})
        return fit

    def _offline_activity(self, fit_path: str, fit: FitData) -> Activity:
        if isinstance(fit.start_time, (datetime.datetime, datetime.date)):
            activity_date = fit.start_time.date().isoformat() if isinstance(fit.start_time, datetime.datetime) else fit.start_time.isoformat()
        else:
            date_match = re.search(r"\d{4}-\d{2}-\d{2}", os.path.basename(fit_path))
            if not date_match:
                raise ValueError("The FIT file does not contain a start date and its filename does not include one.")
            activity_date = date_match.group(0)

        stem = os.path.splitext(os.path.basename(fit_path))[0]
        activity_id_match = re.search(r"(?:^|_)(\d+)(?:_|$)", stem)
        activity_id = activity_id_match.group(1) if activity_id_match else ""
        fallback_name = re.sub(r"_ACTIVITY$", "", stem, flags=re.IGNORECASE)
        fallback_name = re.sub(r"^\d{4}-\d{2}-\d{2}_", "", fallback_name)
        fallback_name = re.sub(r"_\d{4}-\d{2}-\d{2}", "", fallback_name)
        if activity_id:
            fallback_name = re.sub(r"(?:^|_)%s$" % re.escape(activity_id), "", fallback_name)
        name = fit.activity_name or fallback_name or "activity"
        activity_type = self._fit_activity_type(fit.sport)
        if activity_type is None:
            normalized = stem.lower()
            if "run" in normalized:
                activity_type = "running"
            elif "cycl" in normalized or "bike" in normalized:
                activity_type = "cycling"
        if activity_type is None:
            value = input(
                "FIT activity type is not identifiable. Enter c for cycling, r for running: "
            ).strip().lower()
            if value in {"c", "cycling"}:
                activity_type = "cycling"
            elif value in {"r", "running"}:
                activity_type = "running"
            else:
                raise ValueError("Choose c/cycling or r/running for the FIT file.")
        return Activity(
            activity_id=activity_id,
            name=name,
            activity_type=activity_type,
            activity_date=activity_date,
        )

    @staticmethod
    def _fit_activity_type(sport: object) -> str | None:
        normalized = str(sport or "").lower()
        if "run" in normalized:
            return "running"
        if "cycl" in normalized or "bik" in normalized:
            return "cycling"
        return None


class OfflineWorkflow:
    def __init__(self, workflow: ConversionWorkflow):
        self.workflow = workflow

    @staticmethod
    def find_fit_files(path: str) -> list[str]:
        if os.path.isfile(path):
            if not path.lower().endswith(".fit"):
                raise ValueError("Offline input file must have a .fit extension: %s" % path)
            return [path]
        if not os.path.isdir(path):
            raise FileNotFoundError("FIT file or search directory does not exist: %s" % path)
        files = []
        for current, directories, names in os.walk(path):
            directories[:] = sorted(name for name in directories if name not in {".git", ".venv", "__pycache__"})
            files.extend(os.path.join(current, name) for name in names if name.lower().endswith(".fit"))
        return sorted(files)

    def run(self, path: str, automatic: bool) -> None:
        processed: set[str] = set()
        while True:
            files = [file for file in self.find_fit_files(path) if file not in processed]
            if not files:
                print("No more FIT files to review.")
                return
            if automatic:
                for index, file in enumerate(files, start=1):
                    print("%d. %s" % (index, file))
                indices = self.workflow.ui.prompt_activity_selection(len(files))
                if indices is None:
                    return
                if not indices:
                    continue
                for index in indices:
                    processed.add(files[index])
                    self.workflow.convert_offline(files[index], automatic=True)
                return
            selected = None
            for index, file in enumerate(files, start=1):
                print("%d. %s" % (index, file))
                answer = input("Is this the activity to convert? [y/N/q]: ").strip().lower()
                processed.add(file)
                if answer == "q":
                    return
                if answer in {"y", "yes", "t", "tak"}:
                    selected = file
                    break
            if selected is None:
                print("No FIT file was selected.")
                return
            self.workflow.convert_offline(selected, automatic=False)
