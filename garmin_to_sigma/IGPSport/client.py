"""iGPSPORT activity source.

iGPSPORT does not currently publish the web activity API used here as a stable
third-party API.  These endpoints are the same private web endpoints used by
the iGPSPORT web application and may change independently of this project.
"""

import datetime
import math
import os
import re
from dataclasses import replace
from typing import Any

import requests

from ..Utils.gpx import FitGpxWriter
from ..models import Activity
from ..naming import ActivityFileNamer


class IGPSportClient:
    """Client for the iGPSPORT web activity API."""

    REGION_CONFIG = {
        "global": {
            "base_url": "https://prod.en.igpsport.com/service",
            "origin": "https://login.passport.igpsport.com",
            "referer": "https://login.passport.igpsport.com/",
        },
        "cn": {
            "base_url": "https://prod.zh.igpsport.com/service",
            "origin": "https://login.passport.igpsport.cn",
            "referer": "https://login.passport.igpsport.cn/",
        },
    }

    def __init__(
        self,
        username: str,
        password: str,
        activities_dir: str,
        region: str = "global",
        base_url: str | None = None,
        session: requests.Session | None = None,
    ):
        self.username = username
        self.password = password
        self.activities_dir = activities_dir
        self.region = (region or "global").lower()
        if self.region not in self.REGION_CONFIG:
            raise ValueError(
                "Unsupported iGPSPORT region %r. Use global or cn." % self.region
            )
        region_config = self.REGION_CONFIG[self.region]
        self.base_url = (
            base_url or os.environ.get("IGPSPORT_BASE_URL") or region_config["base_url"]
        ).rstrip("/")
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/133.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Content-Type": "application/json",
                "Origin": region_config["origin"],
                "Referer": region_config["referer"],
            }
        )
        self.namer = ActivityFileNamer()
        self.gpx_writer = FitGpxWriter()
        self.token: str | None = None
        self._details: dict[str, dict] = {}

    def login(self) -> None:
        response = self.session.post(
            "%s/auth/account/login" % self.base_url,
            json={
                "username": self.username,
                "password": self.password,
                "appId": os.environ.get("IGPSPORT_APP_ID", "igpsport-web"),
            },
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("code") not in (None, 0, "0"):
            raise RuntimeError(
                "iGPSPORT login failed: %s"
                % payload.get("message", payload.get("msg", "unknown error"))
            )
        token = self._find_value(payload, {"access_token", "accessToken", "token"})
        if not token:
            raise RuntimeError("iGPSPORT login response does not contain an access token.")
        self.token = str(token)
        self.session.headers.update({"Authorization": "Bearer %s" % self.token})

    def list_activities(self, start_date: datetime.date) -> list[Activity]:
        activities_by_id: dict[str, Activity] = {}
        page_no = 1
        page_size = 20
        seen_pages: set[tuple[str, ...]] = set()

        while True:
            payload = self._get_json(
                "/web-gateway/web-analyze/activity/queryMyActivity",
                params={
                    "pageNo": page_no,
                    "pageSize": page_size,
                    "reqType": 0,
                    "sort": 1,
                },
            )
            rows = self._activity_rows(payload)
            if not rows:
                break
            page_ids = tuple(
                str(self._first(row, "rideId", "RideId", "activityId", "id", default=""))
                for row in rows
            )
            if page_ids in seen_pages:
                break
            seen_pages.add(page_ids)

            for row in rows:
                if not isinstance(row, dict):
                    continue
                try:
                    activity = self.to_activity(row)
                except ValueError:
                    continue
                if activity.activity_date < start_date.isoformat():
                    continue
                if activity.activity_type not in {"cycling", "running"}:
                    continue
                if activity.activity_id and not self.is_cached(activity):
                    activities_by_id[activity.activity_id] = activity

            if len(rows) < page_size:
                break
            page_no += 1

        return sorted(
            activities_by_id.values(), key=lambda activity: activity.start_time_local
        )

    def get_details(self, activity_id: str) -> dict:
        key = str(activity_id)
        if key not in self._details:
            self._details[key] = self._get_json(
                "/web-gateway/web-analyze/activity/queryActivityDetail/%s" % key
            )
        return self._details[key]

    def enrich_activity(self, activity: Activity, details: dict) -> Activity:
        activity_type = self.activity_type(details) or activity.activity_type
        values: dict[str, Any] = {
            "name": self._first(details, "activityName", "title", "name", default=activity.name),
            "activity_type": activity_type,
            "start_time_local": self._display_time(
                self._first(
                    details,
                    "startTimeLocal",
                    "startTime",
                    "StartTime",
                    default=activity.start_time_local,
                )
            ),
        }
        for field_name, keys in {
            "distance": (
                "distance",
                "rideDistance",
                "totalDistance",
                "total_distance",
            ),
            "duration": ("totalTime", "duration", "total_timer_time"),
            "elevation_gain": (
                "elevationGain",
                "totalAscent",
                "total_ascent",
                "ascent",
            ),
            "elevation_loss": (
                "elevationLoss",
                "totalDescent",
                "total_descent",
                "descent",
            ),
            "max_elevation": ("maxElevation", "maxAltitude", "max_altitude"),
            "min_elevation": ("minElevation", "minAltitude", "min_altitude"),
        }.items():
            value = self._first(details, *keys, default=None)
            if value is not None:
                values[field_name] = self._number(value)
        return replace(activity, **values)

    def get_weather(self, activity_id: str) -> dict:
        """Return weather fields if the activity detail contains any.

        iGPSPORT does not expose a separate weather endpoint in the private
        activity API. FIT temperature remains the primary source; a missing
        value is handled by the existing user prompt in the workflow.
        """

        details = self.get_details(activity_id)
        weather = details.get("weather") if isinstance(details, dict) else None
        if isinstance(weather, (dict, list)):
            return weather
        temperature = self._first(
            details,
            "temperatureCelsius",
            "temperature_celsius",
            default=None,
        )
        if temperature is None:
            return {}
        return {"temperatureCelsius": temperature}

    def is_cached(self, activity: Activity) -> bool:
        path = os.path.join(
            self.activities_dir,
            self.namer.fit_name(
                activity.name, activity.activity_id, activity.activity_date
            ),
        )
        return os.path.isfile(path) and os.path.getsize(path) > 0

    def download_fit(self, activity: Activity) -> str:
        os.makedirs(self.activities_dir, exist_ok=True)
        path = os.path.join(
            self.activities_dir,
            self.namer.fit_name(
                activity.name, activity.activity_id, activity.activity_date
            ),
        )
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            print("Using downloaded activity file: %s" % path)
            return path

        details = self.get_details(activity.activity_id)
        download_url = self._first(
            details,
            "fitUrl",
            "fitOssPath",
            "fitFileUrl",
            "downloadUrl",
            default=None,
        )
        if not download_url:
            payload = self._get_json(
                "/web-gateway/web-analyze/activity/getDownloadUrl/%s"
                % activity.activity_id
            )
            download_url = self._download_url_from_payload(payload)
        if not download_url:
            raise ValueError(
                "iGPSPORT did not return a FIT download URL for activity %s."
                % activity.activity_id
            )
        data = self._download_bytes(str(download_url))
        if not data:
            raise ValueError(
                "iGPSPORT returned an empty FIT file for activity %s."
                % activity.activity_id
            )
        self._write_bytes(path, data)
        print("Downloaded activity file: %s" % path)
        return path

    def download_gpx(self, activity: Activity) -> str:
        os.makedirs(self.activities_dir, exist_ok=True)
        path = os.path.join(
            self.activities_dir,
            self.namer.gpx_name(
                activity.name, activity.activity_id, activity.activity_date
            ),
        )
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            print("Using downloaded activity GPX: %s" % path)
            return path

        details = self.get_details(activity.activity_id)
        gpx_url = self._first(
            details,
            "gpxUrl",
            "gpxOssPath",
            "gpxFileUrl",
            "downloadGpxUrl",
            default=None,
        )
        if gpx_url:
            data = self._download_bytes(str(gpx_url))
            if data:
                self._write_bytes(path, data)
                print("Downloaded activity GPX: %s" % path)
                return path

        # The current private API normally exposes FIT only.  The FIT has the
        # complete GPS record stream, so create the same GPX artefact locally.
        fit_path = self.download_fit(activity)
        self.gpx_writer.write(fit_path, path, activity.name)
        print("Created activity GPX from FIT: %s" % path)
        return path

    def _get_json(self, path: str, params: dict | None = None) -> Any:
        response = self.session.get(
            "%s%s" % (self.base_url, path), params=params, timeout=30
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict) and payload.get("code") not in (None, 0, "0"):
            raise RuntimeError(
                "iGPSPORT API request failed: %s"
                % payload.get("message", payload.get("msg", "unknown error"))
            )
        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload

    def _download_bytes(self, url: str) -> bytes:
        response = self.session.get(url, timeout=60)
        response.raise_for_status()
        return response.content

    @staticmethod
    def _write_bytes(path: str, data: bytes) -> None:
        temporary_path = "%s.tmp" % path
        try:
            with open(temporary_path, "wb") as output:
                output.write(data)
            os.replace(temporary_path, path)
        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)

    @classmethod
    def _activity_rows(cls, payload: Any) -> list[dict]:
        if isinstance(payload, list):
            return payload
        if not isinstance(payload, dict):
            return []
        for key in ("rows", "items", "list", "records"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return []

    @classmethod
    def to_activity(cls, data: dict) -> Activity:
        activity_id = cls._first(
            data, "rideId", "RideId", "activityId", "id", default=""
        )
        activity_id = str(activity_id)
        activity_type = cls.activity_type(data) or "cycling"
        start_value = cls._first(
            data,
            "startTimeLocal",
            "startTime",
            "StartTime",
            "activityDate",
            "date",
            default=None,
        )
        activity_date = cls._activity_date(start_value)
        return Activity(
            activity_id=activity_id,
            name=str(
                cls._first(
                    data,
                    "activityName",
                    "title",
                    "Title",
                    "name",
                    "ActivityName",
                    default=activity_type.title(),
                )
                or activity_type.title()
            ),
            activity_type=activity_type,
            activity_date=activity_date,
            start_time_local=cls._display_time(start_value),
            distance=cls._number(
                cls._first(
                    data, "distance", "rideDistance", "totalDistance", default=None
                )
            ),
            duration=cls._number(
                cls._first(data, "totalTime", "duration", default=None)
            ),
            elevation_gain=cls._number(
                cls._first(data, "elevationGain", "totalAscent", default=None)
            ),
            elevation_loss=cls._number(
                cls._first(data, "elevationLoss", "totalDescent", default=None)
            ),
            max_elevation=cls._number(
                cls._first(data, "maxElevation", "maxAltitude", default=None)
            ),
            min_elevation=cls._number(
                cls._first(data, "minElevation", "minAltitude", default=None)
            ),
        )

    @staticmethod
    def activity_type(data: dict) -> str | None:
        labels: list[str] = []
        for key in (
            "sport",
            "sportType",
            "sportName",
            "sportTypeName",
            "activityType",
            "activityTypeName",
            "type",
            "typeName",
        ):
            value = data.get(key)
            if isinstance(value, dict):
                labels.extend(str(item) for item in value.values())
            elif value is not None:
                labels.append(str(value))
        normalized = " ".join(labels).lower()
        if "run" in normalized or "跑" in normalized:
            return "running"
        if (
            "cycl" in normalized
            or "bik" in normalized
            or "ride" in normalized
            or "骑" in normalized
        ):
            return "cycling"
        numeric_labels = {str(label).strip() for label in labels}
        if numeric_labels & {"3", "4"}:
            return "cycling"
        if numeric_labels & {"1", "2"}:
            return "running"
        return None

    @classmethod
    def _activity_date(cls, value: Any) -> str:
        if value is None or str(value).strip() == "":
            raise ValueError("iGPSPORT activity does not include a start date.")
        parsed = cls._parse_datetime(value)
        return parsed.date().isoformat()

    @classmethod
    def _display_time(cls, value: Any) -> str:
        if value is None or str(value).strip() == "":
            return ""
        try:
            return cls._parse_datetime(value).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            return str(value)

    @staticmethod
    def _parse_datetime(value: Any) -> datetime.datetime:
        if isinstance(value, datetime.datetime):
            return value
        if isinstance(value, datetime.date):
            return datetime.datetime.combine(value, datetime.time())
        if isinstance(value, (int, float)):
            timestamp = float(value)
            if timestamp > 10_000_000_000:
                timestamp /= 1000
            return datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc).replace(
                tzinfo=None
            )
        text = str(value).strip()
        if re_match := re.match(r"^(\d{4})[.]([01]\d)[.]([0-3]\d)$", text):
            return datetime.datetime(
                int(re_match.group(1)), int(re_match.group(2)), int(re_match.group(3))
            )
        normalized = text.replace("Z", "+00:00")
        try:
            parsed = datetime.datetime.fromisoformat(normalized)
        except ValueError as error:
            raise ValueError("Invalid iGPSPORT activity date: %s" % value) from error
        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)
        return parsed

    @staticmethod
    def _number(value: Any) -> float | None:
        if value is None or value == "":
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if math.isfinite(number) else None

    @classmethod
    def _first(cls, data: Any, *keys: str, default: Any = None) -> Any:
        if isinstance(data, dict):
            for key in keys:
                if key in data and data[key] is not None:
                    return data[key]
            for value in data.values():
                nested = cls._first(value, *keys, default=None)
                if nested is not None:
                    return nested
        elif isinstance(data, list):
            for value in data:
                nested = cls._first(value, *keys, default=None)
                if nested is not None:
                    return nested
        return default

    @classmethod
    def _find_value(cls, data: Any, keys: set[str]) -> Any:
        if isinstance(data, dict):
            for key, value in data.items():
                if key in keys and value:
                    return value
            for value in data.values():
                found = cls._find_value(value, keys)
                if found:
                    return found
        elif isinstance(data, list):
            for value in data:
                found = cls._find_value(value, keys)
                if found:
                    return found
        return None

    @classmethod
    def _download_url_from_payload(cls, payload: Any) -> str | None:
        if isinstance(payload, str) and payload.startswith(("http://", "https://")):
            return payload
        value = cls._find_value(
            payload, {"url", "fiturl", "fitUrl", "downloadurl", "downloadUrl"}
        )
        return str(value) if value else None
