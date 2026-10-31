"""Object-oriented Sigma SMF generation."""

import datetime
import os
import xml.etree.ElementTree as ET

from ..models import ActivityMetadata, FitData


class SmfWriter:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir

    def write_running(
        self, fit_data: FitData, metadata: ActivityMetadata, activity_id: str
    ) -> str:
        print("Saving running to smf file ...")
        root = self._build_activity(fit_data, metadata, activity_id, "Running", "running")
        return self._save(root, metadata.file_name)

    def write_cycling(
        self, fit_data: FitData, metadata: ActivityMetadata, activity_id: str
    ) -> str:
        print("Saving running to smf file ...")
        root = self._build_activity(fit_data, metadata, activity_id, "Cycling", None)
        return self._save(root, metadata.file_name)

    def _build_activity(
        self,
        fit: FitData,
        metadata: ActivityMetadata,
        activity_id: str,
        computer_activity_type: str,
        sport: str | None,
    ) -> ET.Element:
        root = ET.Element("Activity")
        root.set("fileDate", datetime.datetime.now().strftime("%a %b %d %H:%M:%S GMT%z %Y"))
        root.set("revision", "400")
        computer = ET.SubElement(root, "Computer")
        computer.set("unit", "user defined")
        computer.set("serial", "")
        computer.set("activityType", computer_activity_type)
        computer.set("dateCode", "")

        info = ET.SubElement(root, "GeneralInformation")
        self._text(info, "user", "Standard")
        if sport is not None:
            self._text(info, "sport", sport)
        self._text(info, "GUID", "0")
        self._text(info, "modificationDateDeviceSync", "0")
        self._text(info, "altitudeDifferencesDownhill", fit.total_descent * 1000)
        self._text(info, "altitudeDifferencesUphill", fit.total_ascent * 1000)
        self._text(info, "maximumAltitude", fit.max_altitude * 1000)
        self._text(info, "averageHeartrate", fit.avg_heart_rate)
        self._text(info, "maximumHeartrate", fit.max_heart_rate)
        self._text(info, "hrMax", "300")
        self._text(info, "averageSpeed", float(fit.avg_speed))
        self._text(info, "maximumSpeed", float(fit.max_speed))
        self._text(info, "calibration", "false")
        self._text(info, "calories", fit.total_calories)
        self._text(info, "dataType", "memory")
        self._text(info, "description", "description")
        self._text(info, "distance", float(fit.total_distance))
        self._text(info, "externalLink", "https://connect.garmin.com/modern/activity/%s" % activity_id)
        self._text(info, "linkedRouteId", "0")
        self._text(info, "logVersion", "400")
        self._text(info, "manualTemperature", metadata.temperature)
        self._text(info, "name", metadata.file_name)
        self._text(info, "pauseTime", "")
        self._text(info, "rating", metadata.evaluation)
        self._text(info, "feeling", metadata.feelings)
        self._text(info, "samplingRate", "")
        self._text(info, "startDate", fit.start_time.strftime("%a %b %d %H:%M:%S GMT%z %Y"))
        self._text(info, "statistic", "true")
        self._text(info, "timeOverZone", "0")
        self._text(info, "timeUnderZone", "0")
        self._text(info, "trackProfile", metadata.trip_profile)
        self._text(info, "trainingType", "training type")
        self._text(info, "trainingTime", fit.total_timer_time * 100)
        self._text(info, "unitId", "")
        self._text(info, "weather", metadata.weather)
        self._text(info, "wind", metadata.wind)
        self._text(info, "activityStatus", "none")
        self._text(info, "activityTrackerDayComplete", "false")
        ET.SubElement(info, "compGUID")
        self._text(info, "compStartDate", "0")
        ET.SubElement(info, "compName")
        self._text(info, "compDistance", "0")
        self._text(info, "compTime", "0")
        self._text(info, "compTransitionDuration", "0")
        self._text(info, "sharingInfo", '{"facebookId":"0","komootId":"0","sigmaStatisticsId":"0","stravaId":"0","trainingPeaksId":"0","twitterId":"0","twoPeaksId":"0"}')
        ET.SubElement(info, "Participant")
        return root

    @staticmethod
    def _text(parent: ET.Element, name: str, value) -> ET.Element:
        element = ET.SubElement(parent, name)
        element.text = str(value)
        return element

    def _save(self, root: ET.Element, file_name: str) -> str:
        os.makedirs(self.output_dir, exist_ok=True)
        path = os.path.join(self.output_dir, "%s.smf" % file_name)
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        return path
