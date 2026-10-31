import datetime
import tempfile
import unittest
from pathlib import Path

from garmin_to_sigma.IGPSport.client import IGPSportClient


class FakeResponse:
    def __init__(self, payload=None, content=b""):
        self.payload = payload
        self.content = content

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.calls = []

    def post(self, url, **kwargs):
        self.calls.append(("POST", url, kwargs))
        return FakeResponse({"code": 0, "data": {"access_token": "test-token"}})

    def get(self, url, **kwargs):
        self.calls.append(("GET", url, kwargs))
        if url.endswith("queryMyActivity"):
            return FakeResponse(
                {
                    "code": 0,
                    "data": {
                        "rows": [
                            {
                                "RideId": 123,
                                "StartTime": "2026.10.01",
                                "Title": "Morning ride",
                                "Sport": 3,
                                "rideDistance": 12500,
                                "totalTime": 3600,
                            }
                        ]
                    },
                }
            )
        if "queryActivityDetail" in url:
            return FakeResponse(
                {
                    "code": 0,
                    "data": {
                        "activityName": "Morning ride",
                        "startTime": "2026-10-01T08:00:00Z",
                        "totalTime": 3600,
                        "totalAscent": 120,
                    },
                }
            )
        if "getDownloadUrl" in url:
            return FakeResponse({"code": 0, "data": "https://files.test/activity.fit"})
        if url == "https://files.test/activity.fit":
            return FakeResponse(content=b"fit-data")
        raise AssertionError("unexpected URL: %s" % url)


class IGPSportClientTests(unittest.TestCase):
    def test_login_and_list_activity_use_current_api_shape(self):
        session = FakeSession()
        with tempfile.TemporaryDirectory() as directory:
            client = IGPSportClient(
                "user",
                "password",
                directory,
                region="global",
                base_url="https://api.test/service",
                session=session,
            )
            client.login()
            activities = client.list_activities(datetime.date(2026, 10, 1))

        self.assertEqual(client.token, "test-token")
        self.assertEqual(session.headers["Authorization"], "Bearer test-token")
        self.assertEqual(len(activities), 1)
        self.assertEqual(activities[0].activity_id, "123")
        self.assertEqual(activities[0].activity_type, "cycling")
        self.assertEqual(activities[0].activity_date, "2026-10-01")
        self.assertEqual(activities[0].start_time_local, "2026-10-01 00:00:00")
        self.assertEqual(activities[0].distance, 12500)

    def test_details_enrich_activity_and_fit_fallback_download(self):
        session = FakeSession()
        with tempfile.TemporaryDirectory() as directory:
            client = IGPSportClient(
                "user",
                "password",
                directory,
                base_url="https://api.test/service",
                session=session,
            )
            activity = client.to_activity(
                {
                    "RideId": 123,
                    "StartTime": "2026.10.01",
                    "Title": "Morning ride",
                    "Sport": 3,
                }
            )
            details = client.get_details(activity.activity_id)
            enriched = client.enrich_activity(activity, details)
            path = client.download_fit(enriched)

            self.assertEqual(enriched.duration, 3600)
            self.assertEqual(enriched.elevation_gain, 120)
            self.assertEqual(Path(path).read_bytes(), b"fit-data")
            self.assertTrue(Path(path).name.endswith("_123_ACTIVITY.fit"))
            self.assertEqual(
                len([call for call in session.calls if "queryActivityDetail" in call[1]]),
                1,
            )


if __name__ == "__main__":
    unittest.main()
