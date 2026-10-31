"""Activity file naming."""

import re


class ActivityFileNamer:
    def make_stem(self, activity_name: str, activity_id: str, activity_date: str) -> str:
        safe_name = re.sub(
            r'[<>:"/\\|?*\x00-\x1f]', "_", activity_name
        ).strip(" .")
        if not safe_name:
            safe_name = "activity"
        parts = [activity_date, safe_name]
        if activity_id:
            parts.append(activity_id)
        return "_".join(parts)

    def fit_name(self, activity_name: str, activity_id: str, activity_date: str) -> str:
        return "%s_ACTIVITY.fit" % self.make_stem(activity_name, activity_id, activity_date)

    def gpx_name(self, activity_name: str, activity_id: str, activity_date: str) -> str:
        return "%s.gpx" % self.make_stem(activity_name, activity_id, activity_date)

    def smf_name(self, activity_name: str, activity_id: str, activity_date: str) -> str:
        return "%s.smf" % self.make_stem(activity_name, activity_id, activity_date)
