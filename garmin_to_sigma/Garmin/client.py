"""Garmin Connect activity source."""

import datetime
import io
import os
import shutil
import zipfile

from garminconnect import Garmin
from garminconnect.api.activities import ActivityDownloadFormat

from ..models import Activity
from ..naming import ActivityFileNamer


class GarminClient:
    def __init__(self, token_dir: str, activities_dir: str):
        self.token_dir = token_dir
        self.activities_dir = activities_dir
        self.namer = ActivityFileNamer()
        self.client = Garmin()

    def login(self) -> None:
        self.client.login(self.token_dir)

    @staticmethod
    def activity_type(data: dict) -> str | None:
        activity_type = data.get("activityType", {})
        if isinstance(activity_type, dict):
            labels = (
                activity_type.get("typeKey", ""),
                activity_type.get("typeDescription", ""),
                activity_type.get("parentTypeKey", ""),
            )
        else:
            labels = (activity_type or "",)
        dto = data.get("activityTypeDTO", {})
        if isinstance(dto, dict):
            labels += (dto.get("typeKey", ""), dto.get("typeDescription", ""))
        labels += (data.get("sport", ""), data.get("activity_type", ""))
        normalized = " ".join(str(label).lower() for label in labels)
        if "run" in normalized:
            return "running"
        if "cycl" in normalized or "bik" in normalized:
            return "cycling"
        return None

    @staticmethod
    def activity_date(data: dict) -> str:
        start_time = data.get("startTimeLocal") or data.get("startTimeGMT")
        if not start_time:
            raise ValueError("Garmin activity does not include a start date.")
        activity_date = str(start_time)[:10]
        try:
            datetime.date.fromisoformat(activity_date)
        except ValueError as error:
            raise ValueError(
                "Garmin activity has an invalid start date: %s" % start_time
            ) from error
        return activity_date

    @classmethod
    def to_activity(cls, data: dict) -> Activity:
        activity_type = cls.activity_type(data)
        if activity_type is None:
            raise ValueError("Garmin activity is not cycling or running.")
        return Activity(
            activity_id=str(data.get("activityId", "")),
            name=data.get("activityName") or activity_type.title(),
            activity_type=activity_type,
            activity_date=cls.activity_date(data),
            start_time_local=str(data.get("startTimeLocal", "")),
            distance=data.get("distance"),
            duration=data.get("duration"),
            elevation_gain=data.get("elevationGain"),
            elevation_loss=data.get("elevationLoss"),
            max_elevation=data.get("maxElevation"),
            min_elevation=data.get("minElevation"),
        )

    def list_activities(self, start_date: datetime.date) -> list[Activity]:
        activities_by_id: dict[str, Activity] = {}
        page_size = 20
        start = 0
        while True:
            page = self.client.get_activities(start, page_size)
            if isinstance(page, dict):
                page = page.get("activityList", [])
            if not page:
                break
            reached_date_boundary = False
            for data in page:
                if self.activity_type(data) not in {"cycling", "running"}:
                    continue
                try:
                    activity = self.to_activity(data)
                except ValueError:
                    continue
                if not activity.activity_id:
                    continue
                if activity.activity_date < start_date.isoformat():
                    reached_date_boundary = True
                    continue
                if not self.is_cached(activity):
                    activities_by_id[activity.activity_id] = activity
            if reached_date_boundary or len(page) < page_size:
                break
            start += page_size
        return sorted(
            activities_by_id.values(), key=lambda activity: activity.start_time_local
        )

    def get_details(self, activity_id: str) -> dict:
        return self.client.get_activity(activity_id)

    def get_weather(self, activity_id: str) -> dict:
        return self.client.get_activity_weather(activity_id)

    def is_cached(self, activity: Activity) -> bool:
        path = os.path.join(
            self.activities_dir,
            self.namer.fit_name(activity.name, activity.activity_id, activity.activity_date),
        )
        return os.path.isfile(path) and os.path.getsize(path) > 0

    def download_fit(self, activity: Activity) -> str:
        os.makedirs(self.activities_dir, exist_ok=True)
        path = os.path.join(
            self.activities_dir,
            self.namer.fit_name(activity.name, activity.activity_id, activity.activity_date),
        )
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            print("Using downloaded activity file: %s" % path)
            return path
        archive_data = self.client.download_activity(
            activity.activity_id, dl_fmt=ActivityDownloadFormat.ORIGINAL
        )
        with zipfile.ZipFile(io.BytesIO(archive_data)) as archive:
            fit_files = [name for name in archive.namelist() if name.lower().endswith(".fit")]
            if not fit_files:
                raise ValueError("The downloaded Garmin activity archive does not contain a FIT file.")
            fit_file = next(
                (name for name in fit_files if name.lower().endswith("_activity.fit")),
                fit_files[0],
            )
            temporary_path = "%s.tmp" % path
            try:
                with archive.open(fit_file) as source, open(temporary_path, "wb") as target:
                    shutil.copyfileobj(source, target)
                os.replace(temporary_path, path)
            finally:
                if os.path.exists(temporary_path):
                    os.remove(temporary_path)
        print("Downloaded activity file: %s" % path)
        return path

    def download_gpx(self, activity: Activity) -> str:
        os.makedirs(self.activities_dir, exist_ok=True)
        path = os.path.join(
            self.activities_dir,
            self.namer.gpx_name(activity.name, activity.activity_id, activity.activity_date),
        )
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            print("Using downloaded activity GPX: %s" % path)
            return path
        data = self.client.download_activity(
            activity.activity_id, dl_fmt=ActivityDownloadFormat.GPX
        )
        if not data:
            raise ValueError(
                "Garmin Connect returned an empty GPX file for activity %s."
                % activity.activity_id
            )
        with open(path, "wb") as output:
            output.write(data)
        print("Downloaded activity GPX: %s" % path)
        return path
