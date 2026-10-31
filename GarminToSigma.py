import fitdecode
import xml.etree.ElementTree as ET
import datetime
import time
import csv
import zipfile
import io
import shutil
import os
import re
import math
import argparse
from garminconnect import Garmin
from garminconnect.api.activities import ActivityDownloadFormat


TOKEN_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "garmin_tokens")
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ACTIVITIES_DIR = os.path.join(PROJECT_DIR, "activities")
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


def _activity_type(activity):
    activity_type = activity.get("activityType", {})
    if isinstance(activity_type, dict):
        labels = (
            activity_type.get("typeKey", ""),
            activity_type.get("typeDescription", ""),
            activity_type.get("parentTypeKey", ""),
        )
    else:
        labels = (activity_type or "",)

    activity_type_dto = activity.get("activityTypeDTO", {})
    if isinstance(activity_type_dto, dict):
        labels += (
            activity_type_dto.get("typeKey", ""),
            activity_type_dto.get("typeDescription", ""),
        )
    labels += (
        activity.get("sport", ""),
        activity.get("activity_type", ""),
    )

    normalized_labels = " ".join(str(label).lower() for label in labels)
    if "run" in normalized_labels:
        return "running"
    if "cycl" in normalized_labels or "bik" in normalized_labels:
        return "cycling"
    return None


def _find_weather_value(data, keys):
    if isinstance(data, dict):
        for key, value in data.items():
            if key.lower() in keys and value is not None:
                return value
        for value in data.values():
            result = _find_weather_value(value, keys)
            if result is not None:
                return result
    elif isinstance(data, list):
        for value in data:
            result = _find_weather_value(value, keys)
            if result is not None:
                return result
    return None


def _sigma_weather_code(weather_data):
    label = _find_weather_value(
        weather_data,
        {
            "desc",
            "weathertypedescription",
            "weatherdescription",
            "weathercondition",
            "conditions",
            "typekey",
        },
    )
    normalized_label = str(label or "").lower().replace(" ", "_").replace("-", "_")
    for weather_name, code in SIGMA_WEATHER_CODES.items():
        if weather_name in normalized_label:
            return code
    return ""


def _weather_description(weather_data):
    return _find_weather_value(
        weather_data,
        {
            "desc",
            "weathertypedescription",
            "weatherdescription",
            "weathercondition",
            "conditions",
        },
    )


def _garmin_temperature_celsius(temperature_fahrenheit):
    if temperature_fahrenheit is None:
        return None
    return (float(temperature_fahrenheit) - 32) * 5 / 9


def _garmin_wind_speed_mps(wind_speed_mph):
    if wind_speed_mph is None:
        return None
    return float(wind_speed_mph) * 0.44704


def _beaufort_code(wind_speed):
    if wind_speed is None:
        return ""
    speed = float(wind_speed)
    limits_mps = (0.3, 1.6, 3.4, 5.5, 8.0, 10.8, 13.9, 17.2, 20.8, 24.5, 28.5, 32.7)
    for code, limit in enumerate(limits_mps):
        if speed < limit:
            return code
    return 12


def _elevation_per_km(fit_result):
    try:
        total_distance = float(fit_result.get("total_distance"))
        total_ascent = float(fit_result.get("total_ascent"))
        total_descent = float(fit_result.get("total_descent"))
    except (TypeError, ValueError):
        return 0

    if (
        not math.isfinite(total_distance)
        or not math.isfinite(total_ascent)
        or not math.isfinite(total_descent)
        or total_distance <= 0
    ):
        return None

    return max(total_ascent, total_descent) / (total_distance / 1000)


def _trip_profile_from_elevation(fit_result):
    """Return Sigma's track profile based on elevation gain per kilometre."""
    elevation_per_km = _elevation_per_km(fit_result)
    if elevation_per_km is None:
        return 0

    if elevation_per_km < 15:
        return 0
    if elevation_per_km < 30:
        return 1
    if elevation_per_km < 50:
        return 2
    if elevation_per_km < 80:
        return 3
    return 4


def _score_from_thresholds(value, thresholds):
    for score, threshold in enumerate(thresholds):
        if value < threshold:
            return score
    return len(thresholds)


def _evaluation_from_activity(fit_result, activity_type):
    """Return a 0-5 activity evaluation from speed, distance and elevation."""
    try:
        distance_km = float(fit_result.get("total_distance")) / 1000
        average_speed_kmh = float(fit_result.get("avg_speed")) * 3.6
    except (TypeError, ValueError):
        return 0

    if (
        not math.isfinite(distance_km)
        or not math.isfinite(average_speed_kmh)
        or distance_km <= 0
        or average_speed_kmh < 0
    ):
        return 0

    if activity_type == "running":
        speed_score = _score_from_thresholds(
            average_speed_kmh, (6, 8, 10, 12, 14)
        )
        distance_score = _score_from_thresholds(
            distance_km, (3, 5, 10, 15, 25)
        )
    else:
        speed_score = _score_from_thresholds(
            average_speed_kmh, (15, 18, 22, 26, 30)
        )
        distance_score = _score_from_thresholds(
            distance_km, (10, 25, 50, 80, 120)
        )

    elevation_per_km = _elevation_per_km(fit_result)
    elevation_score = (
        0
        if elevation_per_km is None
        else _score_from_thresholds(elevation_per_km, (15, 30, 50, 80, 120))
    )
    weighted_score = (
        0.5 * speed_score
        + 0.3 * distance_score
        + 0.2 * elevation_score
    )
    return min(5, int(weighted_score + 0.5))


def _prompt_temperature():
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


def _activity_date(activity):
    start_time = activity.get("startTimeLocal") or activity.get("startTimeGMT")
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


def _safe_activity_name(activity_name, activity_id, activity_date):
    safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", activity_name).strip(" .")
    if not safe_name:
        safe_name = "activity"
    parts = [activity_date, safe_name]
    if activity_id:
        parts.append(activity_id)
    return "_".join(parts)


def _activity_fit_is_cached(activity):
    activity_id = str(activity.get("activityId", ""))
    if not activity_id:
        return False

    try:
        activity_date = _activity_date(activity)
    except ValueError:
        return False

    activity_name = activity.get("activityName") or "activity"
    fit_path = os.path.join(
        ACTIVITIES_DIR,
        "%s_ACTIVITY.fit"
        % _safe_activity_name(activity_name, activity_id, activity_date),
    )
    if os.path.isfile(fit_path) and os.path.getsize(fit_path) > 0:
        return True
    return False


def _apply_garmin_elevation_stats(fit_result, activity):
    fields = {
        "max_altitude": "maxElevation",
        "min_altitude": "minElevation",
        "total_ascent": "elevationGain",
        "total_descent": "elevationLoss",
    }
    for fit_field, garmin_field in fields.items():
        value = activity.get(garmin_field)
        if value is None:
            continue
        try:
            numeric_value = float(value)
        except (TypeError, ValueError) as error:
            raise ValueError(
                "Garmin Connect returned an invalid %s value." % garmin_field
            ) from error
        if not math.isfinite(numeric_value):
            raise ValueError(
                "Garmin Connect returned a non-finite %s value." % garmin_field
            )
        fit_result[fit_field] = numeric_value


def _download_activity_fit(garmin, activity_id, activity_date, activity_name):
    fit_path = os.path.join(
        ACTIVITIES_DIR,
        "%s_ACTIVITY.fit"
        % _safe_activity_name(activity_name, activity_id, activity_date),
    )
    if os.path.isfile(fit_path) and os.path.getsize(fit_path) > 0:
        print("Using downloaded activity file: %s" % fit_path)
        return fit_path

    archive_data = garmin.download_activity(
        activity_id,
        dl_fmt=ActivityDownloadFormat.ORIGINAL,
    )
    with zipfile.ZipFile(io.BytesIO(archive_data)) as activity_archive:
        fit_files = [
            name for name in activity_archive.namelist()
            if name.lower().endswith(".fit")
        ]
        if not fit_files:
            raise ValueError(
                "The downloaded Garmin activity archive does not contain a FIT file."
            )

        fit_file = next(
            (name for name in fit_files if name.lower().endswith("_activity.fit")),
            fit_files[0],
        )
        temporary_path = "%s.tmp" % fit_path
        try:
            with activity_archive.open(fit_file) as source, open(temporary_path, "wb") as target:
                shutil.copyfileobj(source, target)
            os.replace(temporary_path, fit_path)
        finally:
            if os.path.exists(temporary_path):
                os.remove(temporary_path)

    print("Downloaded activity file: %s" % fit_path)
    return fit_path


def _download_activity_gpx(garmin, activity_id, file_name):
    gpx_path = os.path.join(ACTIVITIES_DIR, "%s.gpx" % file_name)
    if os.path.isfile(gpx_path) and os.path.getsize(gpx_path) > 0:
        print("Using downloaded activity GPX: %s" % gpx_path)
        return gpx_path

    gpx_data = garmin.download_activity(
        activity_id,
        dl_fmt=ActivityDownloadFormat.GPX,
    )
    if not gpx_data:
        raise ValueError(
            "Garmin Connect returned an empty GPX file for activity %s."
            % activity_id
        )

    with open(gpx_path, "wb") as gpx_file:
        gpx_file.write(gpx_data)
    print("Downloaded activity GPX: %s" % gpx_path)
    return gpx_path


def konwertujNaFormatCzasu(sekundy):
    godziny = int(sekundy // 3600)
    reszta_sekundy = sekundy % 3600
    minuty = int(reszta_sekundy // 60)
    pozostale_sekundy = int(reszta_sekundy % 60)
    return f"{godziny:02}:{minuty:02}:{pozostale_sekundy:02}"

def konwerujMpSOnKmPh(MetersPerSeconds):
    # Stała przeliczeniowa: 1 m/s = 3.6 km/h
    przelicznik = 3.6
    kilometry_na_godzine = MetersPerSeconds * przelicznik
    return kilometry_na_godzine

def konwertujMpSOnMinPerKm(speed_mps):
    # m/s -> min/km
    if speed_mps <= 0:
        return "Prędkość musi być większa niż 0"

    min_per_km = 1000 / (speed_mps * 60)
    minutes_ = int(min_per_km)
    seconds_ = int(round((min_per_km - minutes_) * 60))

    return datetime.timedelta(minutes=minutes_, seconds=seconds_)

def showResultsFromFit(data):
    for k, v in data.items():
        if k == "total_timer_time":
            print(k, v,"s   ", konwertujNaFormatCzasu(v))
        elif k == "total_distance":
            print(k, v, 'm',)
        elif k in {"avg_temperature", "min_temperature", "max_temperature"}:
            print(k, v, "°C" if v is not None else "(unavailable)")
        elif k == "avg_speed":
            print(k, v, "m/s", konwerujMpSOnKmPh(v), "km/h", str(konwertujMpSOnMinPerKm(v)), "/km" )
        elif k == "max_speed":
            print(k, v, "m/s", konwerujMpSOnKmPh(v), "km/h", str(konwertujMpSOnMinPerKm(v)), "/km" )
        else:
            print (k, v)


def showSmfInputData(fit_result, note, activity_type, activity_id):
    print("\nData passed to the SMF file:")
    print("activity_type:", activity_type)
    print("activity_id:", activity_id)
    print("FIT activity data:")
    showResultsFromFit(fit_result)
    print("SMF metadata:")
    for key, value in note.items():
        if key == "temperature":
            if value in (None, ""):
                print("%s: unavailable" % key)
            else:
                print("%s: %.1f °C" % (key, value))
        elif key == "weather":
            description = note.get("weather_description") or "unknown"
            print("%s: %s (%s)" % (key, value, description))
        elif key == "wind":
            wind_speed = note.get("wind_speed_mph")
            if wind_speed in (None, ""):
                print("%s: %s Beaufort" % (key, value))
            else:
                wind_speed_mps = _garmin_wind_speed_mps(wind_speed)
                print(
                    "%s: %s Beaufort (Garmin: %s mph / %.1f m/s)"
                    % (key, value, wind_speed, wind_speed_mps)
                )
        elif key not in {"weather_description", "wind_speed_mph"}:
            print("%s: %s" % (key, value))


def readFitFile(filename):
    print ("Reading fit file ...")
    result = {}
    minimum_altitudes = []
    maximum_altitudes = []
    record_altitudes = []
    fit_temperatures = []
    minimum_temperatures = []
    maximum_temperatures = []
    fit_average_temperature = None

    with fitdecode.FitReader(filename) as fit:
        for frame in fit:
            if isinstance(frame, fitdecode.FitDataMessage):
                record_altitude = None
                for x in range(len(frame.fields)):
                    field_name = frame.fields[x].name.lower()
                    field_value = frame.fields[x].value
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
                                if (
                                    field_name == "enhanced_altitude"
                                    or record_altitude is None
                                ):
                                    record_altitude = numeric_value
                    if frame.name == "session" and field_name == "avg_heart_rate":
                        if field_value is not None:
                            result["avg_heart_rate"] = field_value
                    if frame.name == "session" and field_name == "max_heart_rate":
                        if field_value is not None:
                            result["max_heart_rate"] = field_value
                    if frame.name == "session" and field_name == "total_timer_time":
                        if field_value is not None:
                            result["total_timer_time"] = field_value
                    if frame.name == "session" and field_name == "total_ascent":
                        if field_value is not None:
                            result["total_ascent"] = field_value
                    if frame.name == "session" and field_name == "total_descent":
                        if field_value is not None:
                            result["total_descent"] = field_value
                    if (
                        frame.name == "session"
                        and field_name in {"max_speed", "enhanced_max_speed"}
                    ):
                        if field_value is not None:
                            if (
                                field_name == "enhanced_max_speed"
                                or "max_speed" not in result
                            ):
                                result["max_speed"] = field_value
                    if (
                        frame.name == "session"
                        and field_name in {"avg_speed", "enhanced_avg_speed"}
                    ):
                        if field_value is not None:
                            if (
                                field_name == "enhanced_avg_speed"
                                or "avg_speed" not in result
                            ):
                                result["avg_speed"] = field_value
                    if frame.name == "session" and field_name == "total_calories":
                        if field_value is not None:
                            result["total_calories"] = field_value
                    if field_name == "start_time":
                        if field_value is not None:
                            result["start_time"] = field_value
                    if field_name == "sport" and field_value is not None:
                        result["sport"] = field_value
                    if field_name in {"name", "activity_name"} and field_value:
                        result["activity_name"] = str(field_value)
                    if frame.name == "session" and field_name == "total_distance":
                        if field_value is not None:
                            result["total_distance"] = field_value
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

    if minimum_altitudes:
        result["min_altitude"] = min(minimum_altitudes)
    elif record_altitudes:
        result["min_altitude"] = min(record_altitudes)
    if maximum_altitudes:
        result["max_altitude"] = max(maximum_altitudes)
    elif record_altitudes:
        result["max_altitude"] = max(record_altitudes)
    if "min_altitude" not in result or "max_altitude" not in result:
        raise ValueError("The FIT file does not contain usable altitude data.")

    if fit_average_temperature is not None:
        result["avg_temperature"] = fit_average_temperature
    elif fit_temperatures:
        result["avg_temperature"] = sum(fit_temperatures) / len(fit_temperatures)
    if minimum_temperatures:
        result["min_temperature"] = min(minimum_temperatures)
    elif fit_temperatures:
        result["min_temperature"] = min(fit_temperatures)
    if maximum_temperatures:
        result["max_temperature"] = max(maximum_temperatures)
    elif fit_temperatures:
        result["max_temperature"] = max(fit_temperatures)
    return result

def readCSVFileBC12(fileName):
    print ("Reading csv file ...")
    result = {"trip_distance":50.0}
    os.path.abspath(os.getcwd())
    file = "%s.csv"%(fileName)
    #fileWithPath = "%s\%s.csv"%(os.path.abspath(os.getcwd()), fileName)
    with open(file) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=';')
        line_count = 0
        for row in csv_reader:
            if line_count == 0:
                line_count += 1
            else:
                result["trip_distance"] = row[0].replace(',','.')
                result["ride_time"] = row[1].replace(',','.')
                result["avg_speed"] = row[2].replace(',','.')
                result["max_speed"] = row[3].replace(',','.')
                result["fuel"] = row[4].replace(',','.')
                result["TS_distance"] = row[5].replace(',','.')
                result["TS_time"] = row[6].replace(',','.')
                result["temperature"] = row[7].replace(',','.')
                result["total_distance"] = row[8].replace(',','.')
                result["total_time"] = row[9].replace(',','.')
                result["total_fuel"] = row[10].replace(',','.')
                line_count += 1

    for k, v in result.items():
        print (k, v)

    return result

def readCSVFileBC16(fileName):
    print ("Reading csv file ...")
    result = {"trip_distance":50.0}
    os.path.abspath(os.getcwd())
    file = "%s.csv"%(fileName)
    #fileWithPath = "%s\%s.csv"%(os.path.abspath(os.getcwd()), fileName)
    with open(file) as csv_file:
        csv_reader = csv.reader(csv_file, delimiter=';')
        line_count = 0
        for row in csv_reader:
            if line_count == 0:
                line_count += 1
            else:
                result["trip_distance"] = row[0].replace(',','.')
                result["ride_time"] = row[1].replace(',','.')
                result["avg_speed"] = row[2].replace(',','.')
                result["max_speed"] = row[3].replace(',','.')
                result["fuel"] = row[4].replace(',','.')
                result["temperature"] = row[5].replace(',','.')
                result["total_distance"] = row[6].replace(',','.')
                result["total_time"] = row[7].replace(',','.')
                result["total_fuel"] = row[8].replace(',','.')
                line_count += 1

    
    for k, v in result.items():     
        print (k, v)

    return result

##    ------------------------  create XML  -------------------------------   ##
def saveToSmfFile(computerBike, fitResult, csvResult, notes, activityNumber):
    print ("Saving to smf file ...")
    root = ET.Element("Activity")

    root.set("fileDate", datetime.datetime.now().strftime('%a %b %d %H:%M:%S GMT%z %Y'))
    root.set("revision", "400")
    computer = ET.SubElement(root,"Computer")
    computer.set("unit","user defined")
    computer.set("serial","")
    computer.set("activityType","Cycling")
    computer.set("dateCode","")

    generalInformation = ET.SubElement(root, "GeneralInformation")
    user = ET.SubElement(generalInformation, "user")
    if computerBike == '1':
        user.text = "Cube Nuroad Pro"
    elif computerBike == '2':
        user.text = "Alu City"

    #sport = ET.SubElement(generalInformation, "sport")
    #sport.text = "test"

    guid = ET.SubElement(generalInformation, "GUID")
    guid.text = "0"

    mdds = ET.SubElement(generalInformation, "modificationDateDeviceSync")
    mdds.text = "0"

    # Altitude uphill [dm]
    altitudeDifferencesDownhill = ET.SubElement(generalInformation, "altitudeDifferencesDownhill")
    altitudeDifferencesDownhill.text = str(fitResult["total_descent"]*1000)

    # Altitude downhill [dm]
    altitudeDifferencesUphill = ET.SubElement(generalInformation, "altitudeDifferencesUphill")
    altitudeDifferencesUphill.text = str(fitResult["total_ascent"]*1000)
    
    # Altitude max
    maximumAltitude = ET.SubElement(generalInformation, "maximumAltitude")
    maximumAltitude.text = str(fitResult["max_altitude"]*1000)

    #Cadence [rpm]
    #averageCadence = ET.SubElement(generalInformation, "averageCadence")
    #averageCadence.text = "1"

    # Heart rate avg
    averageHeartrate = ET.SubElement(generalInformation, "averageHeartrate")
    averageHeartrate.text = str(fitResult["avg_heart_rate"])

    # Hear rate max
    maximumHeartrate = ET.SubElement(generalInformation, "maximumHeartrate")
    maximumHeartrate.text = str(fitResult["max_heart_rate"])
    
    # ?????
    hrMax = ET.SubElement(generalInformation, "hrMax")
    hrMax.text = "300"

    # Incline down [%]
    #averageInclineDownhill = ET.SubElement(generalInformation, "averageInclineDownhill")
    #averageInclineDownhill.text = "2"

    # Incline up [%]
    #averageInclineUphill = ET.SubElement(generalInformation, "averageInclineUphill")
    #averageInclineUphill.text = "3"

    # Incline min [%]
    #maximumInclineDownhill = ET.SubElement(generalInformation, "maximumInclineDownhill")
    #maximumInclineDownhill.text = "44"

    # Incline max [%]
    #maximumInclineUphill = ET.SubElement(generalInformation, "maximumInclineUphill")
    #maximumInclineUphill.text = "55"

    # ?????????
    #averageRiseRateUphill = ET.SubElement(generalInformation, "averageRiseRateUphill")
    #averageRiseRateUphill.text = "4"

    # ???????????
    #averageRiseRateDownhill = ET.SubElement(generalInformation, "averageRiseRateDownhill")
    #averageRiseRateDownhill.text = "5"

    # Speed avg [m/s]
    averageSpeed = ET.SubElement(generalInformation, "averageSpeed")
    averageSpeed.text = str(float (csvResult["avg_speed"]) / 3.6)

    # Speed max [m/s]
    maximumSpeed = ET.SubElement(generalInformation, "maximumSpeed")
    maximumSpeed.text = str(float (csvResult["max_speed"]) / 3.6)

    # Speed uphill [m/s]
    #averageSpeedDownhill = ET.SubElement(generalInformation, "averageSpeedDownhill")
    #averageSpeedDownhill.text = "6"
     
    # Speed downhill [m/s]
    #averageSpeedUphill = ET.SubElement(generalInformation, "averageSpeedUphill")
    #averageSpeedUphill.text = "7"

    bike = ET.SubElement(generalInformation, "bike")
    bike.text = "bike1"

    calibration = ET.SubElement(generalInformation, "calibration")
    calibration.text = "false"

    # Calories [kcal]
    calories = ET.SubElement(generalInformation, "calories")
    calories.text = str(fitResult["total_calories"])

    dataType = ET.SubElement(generalInformation, "dataType")
    dataType.text = "memory"

    # Description
    description = ET.SubElement(generalInformation, "description")
    description.text = "description"

    # Trip distance [m]
    distance = ET.SubElement(generalInformation, "distance")
    distance.text = str(float(csvResult["trip_distance"])*1000.0)

    # Distance downhill
    #distanceDownhill = ET.SubElement(generalInformation, "distanceDownhill")
    #distanceDownhill.text = "0"

    # Distance uphill
    #distanceUphill = ET.SubElement(generalInformation, "distanceUphill")
    #distanceUphill.text = "0"

    externalLink = ET.SubElement(generalInformation, "externalLink")
    externalLink.text = "%s/%s"%("https://connect.garmin.com/modern/activity",activityNumber)

    #Fuel saving
    fuelEconomy = ET.SubElement(generalInformation, "fuelEconomy")
    fuelEconomy.text = str(csvResult["fuel"])


    # Linked Track
    linkedRouteId = ET.SubElement(generalInformation, "linkedRouteId")
    linkedRouteId.text = "0"

    logVersion = ET.SubElement(generalInformation, "logVersion")
    logVersion.text = "400"

    manualTemperature = ET.SubElement(generalInformation, "manualTemperature")
    manualTemperature.text = str(csvResult["temperature"])

    # Cadence max [rpm]
    #maximumCadence = ET.SubElement(generalInformation, "maximumCadence")
    #maximumCadence.text = "0"

    #minimumRiseRate = ET.SubElement(generalInformation, "minimumRiseRate")
    #minimumRiseRate.text = "0"

    #maximumRiseRate = ET.SubElement(generalInformation, "maximumRiseRate")
    #maximumRiseRate.text = "0"

    #minimumTemperature = ET.SubElement(generalInformation, "minimumTemperature")
    #minimumTemperature.text = "400"

    #maximumTemperature = ET.SubElement(generalInformation, "maximumTemperature")
    #maximumTemperature.text = "0"

    name = ET.SubElement(generalInformation, "name")
    name.text = str(notes["file_name"])

    pauseTime = ET.SubElement(generalInformation, "pauseTime")
    pauseTime.text = ""

    # 0-5
    rating = ET.SubElement(generalInformation, "rating")
    rating.text = str(notes["evaluation"])

    # 0-4
    feeling = ET.SubElement(generalInformation, "feeling")
    feeling.text = str(notes["feelings"])


    samplingRate = ET.SubElement(generalInformation, "samplingRate")
    samplingRate.text = ""

    startDate = ET.SubElement(generalInformation, "startDate")
    startDate.text = fitResult["start_time"].strftime('%a %b %d %H:%M:%S GMT%z %Y')

    statistic = ET.SubElement(generalInformation, "statistic")
    statistic.text = "true"

    timeOverZone = ET.SubElement(generalInformation, "timeOverZone")
    timeOverZone.text = "0"

    timeUnderZone = ET.SubElement(generalInformation, "timeUnderZone")
    timeUnderZone.text = "0"

    # 0-4
    trackProfile = ET.SubElement(generalInformation, "trackProfile")
    trackProfile.text = str(notes["trip_profile"])

    # Training type (short info)
    trainingType = ET.SubElement(generalInformation, "trainingType")
    trainingType.text = "training type"

    # training time [ms]
    trainingTime = ET.SubElement(generalInformation, "trainingTime")
    x = time.strptime(csvResult["ride_time"], '%H:%M:%S')
    y = datetime.timedelta(hours=x.tm_hour,minutes=x.tm_min,seconds=x.tm_sec).total_seconds()
    trainingTime.text = str(int(y*100))


    # training time uphill [ms]
    #trainingTimeDownhill = ET.SubElement(generalInformation, "trainingTimeDownhill")
    #trainingTimeDownhill.text = ""
    
    # training time downhill [ms]
    #trainingTimeUphill = ET.SubElement(generalInformation, "trainingTimeUphill")
    #trainingTimeUphill.text = ""

    if computerBike == '2':
        # Section Distance
        tripSectionDistance = ET.SubElement(generalInformation, "tripSectionDistance")
        tripSectionDistance.text = str(float(csvResult["TS_distance"])*1000.0)

        # Section Time
        tripSectionTime = ET.SubElement(generalInformation, "tripSectionTime")
        x = time.strptime(csvResult["TS_time"], '%H:%M:%S')
        y = datetime.timedelta(hours=x.tm_hour,minutes=x.tm_min,seconds=x.tm_sec).total_seconds()
        tripSectionTime.text = str(int(y*100))

    unitId = ET.SubElement(generalInformation, "unitId")
    unitId.text = ""

    # 0-7
    # 0 - sunny
    # 1 - loght cloud
    # 2 - Cloudy
    # 3 - Light rain
    # 4 - Rain
    # 5 - Storm
    # 6 - Snow
    # 7 - fog
    weather = ET.SubElement(generalInformation, "weather")
    weather.text = str(notes["weather"])

    wheelSize = ET.SubElement(generalInformation, "wheelSize")
    wheelSize.text = "0"

    # 0-12
    wind = ET.SubElement(generalInformation, "wind")
    wind.text = str(notes["wind"])

    #zone1Start = ET.SubElement(generalInformation, "zone1Start")
    #zone1Start.text = "15"

    #zone2Start = ET.SubElement(generalInformation, "zone2Start")
    #zone2Start.text = "15"

    #zone3Start = ET.SubElement(generalInformation, "zone3Start")
    #zone3Start.text = "15"

    #zone3End = ET.SubElement(generalInformation, "zone3End")
    #zone3End.text = "0"

    activityStatus = ET.SubElement(generalInformation, "activityStatus")
    activityStatus.text = "none"

    activityTrackerDayComplete = ET.SubElement(generalInformation, "activityTrackerDayComplete")
    activityTrackerDayComplete.text = "false"

    compGUID = ET.SubElement(generalInformation, "compGUID")

    compStartDate = ET.SubElement(generalInformation, "compStartDate")
    compStartDate.text = "0"

    compName = ET.SubElement(generalInformation, "compName")

    compDistance = ET.SubElement(generalInformation, "compDistance")
    compDistance.text = "0"

    compTime = ET.SubElement(generalInformation, "compTime")
    compTime.text = "0"

    compTransitionDuration = ET.SubElement(generalInformation, "compTransitionDuration")
    compTransitionDuration.text = "0"

    sharingInfo = ET.SubElement(generalInformation, "sharingInfo")
    sharingInfo.text = '{"facebookId":"0","komootId":"0","sigmaStatisticsId":"0","stravaId":"0","trainingPeaksId":"0","twitterId":"0","twoPeaksId":"0"}'

    Participant = ET.SubElement(generalInformation, "Participant")

    tree = ET.ElementTree(root)
    file = os.path.join(ACTIVITIES_DIR, "%s.smf" % notes["file_name"])
    tree.write(file, encoding="utf-8", xml_declaration=True)

def saveHikingToSmfFile(fitResult, notes, activityNumber):
    print ("Saving hiking to smf file ...")
    root = ET.Element("Activity")

    root.set("fileDate", datetime.datetime.now().strftime('%a %b %d %H:%M:%S GMT%z %Y'))
    root.set("revision", "400")
    computer = ET.SubElement(root,"Computer")
    computer.set("unit","user defined")
    computer.set("serial","")
    computer.set("activityType","Hiking")
    computer.set("dateCode","")

    generalInformation = ET.SubElement(root, "GeneralInformation")
    user = ET.SubElement(generalInformation, "user")
    user.text = "Standard"

    sport = ET.SubElement(generalInformation, "sport")
    sport.text = "hiking"

    guid = ET.SubElement(generalInformation, "GUID")
    guid.text = "0"

    mdds = ET.SubElement(generalInformation, "modificationDateDeviceSync")
    mdds.text = "0"

    # Altitude uphill [dm]
    altitudeDifferencesDownhill = ET.SubElement(generalInformation, "altitudeDifferencesDownhill")
    altitudeDifferencesDownhill.text = str(fitResult["total_descent"]*1000)

    # Altitude downhill [dm]
    altitudeDifferencesUphill = ET.SubElement(generalInformation, "altitudeDifferencesUphill")
    altitudeDifferencesUphill.text = str(fitResult["total_ascent"]*1000)

    # Altitude max
    maximumAltitude = ET.SubElement(generalInformation, "maximumAltitude")
    maximumAltitude.text = str(fitResult["max_altitude"]*1000)

    #Cadence [rpm]
    #averageCadence = ET.SubElement(generalInformation, "averageCadence")
    #averageCadence.text = "1"

    # Heart rate avg
    averageHeartrate = ET.SubElement(generalInformation, "averageHeartrate")
    averageHeartrate.text = str(fitResult["avg_heart_rate"])

    # Hear rate max
    maximumHeartrate = ET.SubElement(generalInformation, "maximumHeartrate")
    maximumHeartrate.text = str(fitResult["max_heart_rate"])

    # ?????
    hrMax = ET.SubElement(generalInformation, "hrMax")
    hrMax.text = "300"

    # Incline down [%]
    #averageInclineDownhill = ET.SubElement(generalInformation, "averageInclineDownhill")
    #averageInclineDownhill.text = "2"

    # Incline up [%]
    #averageInclineUphill = ET.SubElement(generalInformation, "averageInclineUphill")
    #averageInclineUphill.text = "3"

    # Incline min [%]
    #maximumInclineDownhill = ET.SubElement(generalInformation, "maximumInclineDownhill")
    #maximumInclineDownhill.text = "44"

    # Incline max [%]
    #maximumInclineUphill = ET.SubElement(generalInformation, "maximumInclineUphill")
    #maximumInclineUphill.text = "55"

    # ?????????
    #averageRiseRateUphill = ET.SubElement(generalInformation, "averageRiseRateUphill")
    #averageRiseRateUphill.text = "4"

    # ???????????
    #averageRiseRateDownhill = ET.SubElement(generalInformation, "averageRiseRateDownhill")
    #averageRiseRateDownhill.text = "5"

    # Speed avg [m/s]
    averageSpeed = ET.SubElement(generalInformation, "averageSpeed")
    averageSpeed.text = str(float(fitResult["avg_speed"]))

    # Speed max [m/s]
    maximumSpeed = ET.SubElement(generalInformation, "maximumSpeed")
    maximumSpeed.text = str(float(fitResult["max_speed"]))

    # Speed uphill [m/s]
    #averageSpeedDownhill = ET.SubElement(generalInformation, "averageSpeedDownhill")
    #averageSpeedDownhill.text = "6"

    # Speed downhill [m/s]
    #averageSpeedUphill = ET.SubElement(generalInformation, "averageSpeedUphill")
    #averageSpeedUphill.text = "7"

    calibration = ET.SubElement(generalInformation, "calibration")
    calibration.text = "false"

    # Calories [kcal]
    calories = ET.SubElement(generalInformation, "calories")
    calories.text = str(fitResult["total_calories"])

    dataType = ET.SubElement(generalInformation, "dataType")
    dataType.text = "memory"

    # Description
    description = ET.SubElement(generalInformation, "description")
    description.text = "description"

    # Trip distance [m]
    distance = ET.SubElement(generalInformation, "distance")
    distance.text = str(float(fitResult["total_distance"]))

    # Distance downhill
    #distanceDownhill = ET.SubElement(generalInformation, "distanceDownhill")
    #distanceDownhill.text = "0"

    # Distance uphill
    #distanceUphill = ET.SubElement(generalInformation, "distanceUphill")
    #distanceUphill.text = "0"

    externalLink = ET.SubElement(generalInformation, "externalLink")
    externalLink.text = "%s/%s"%("https://connect.garmin.com/modern/activity",activityNumber)

    # Linked Track
    linkedRouteId = ET.SubElement(generalInformation, "linkedRouteId")
    linkedRouteId.text = "0"

    logVersion = ET.SubElement(generalInformation, "logVersion")
    logVersion.text = "400"

    manualTemperature = ET.SubElement(generalInformation, "manualTemperature")
    manualTemperature.text = str(notes["temperature"])

    # Cadence max [rpm]
    #maximumCadence = ET.SubElement(generalInformation, "maximumCadence")
    #maximumCadence.text = "0"

    #minimumRiseRate = ET.SubElement(generalInformation, "minimumRiseRate")
    #minimumRiseRate.text = "0"

    #maximumRiseRate = ET.SubElement(generalInformation, "maximumRiseRate")
    #maximumRiseRate.text = "0"

    #minimumTemperature = ET.SubElement(generalInformation, "minimumTemperature")
    #minimumTemperature.text = "400"

    #maximumTemperature = ET.SubElement(generalInformation, "maximumTemperature")
    #maximumTemperature.text = "0"

    name = ET.SubElement(generalInformation, "name")
    name.text = str(notes["file_name"])

    pauseTime = ET.SubElement(generalInformation, "pauseTime")
    pauseTime.text = ""

    # 0-5
    rating = ET.SubElement(generalInformation, "rating")
    rating.text = str(notes["evaluation"])

    # 0-4
    feeling = ET.SubElement(generalInformation, "feeling")
    feeling.text = str(notes["feelings"])


    samplingRate = ET.SubElement(generalInformation, "samplingRate")
    samplingRate.text = ""

    startDate = ET.SubElement(generalInformation, "startDate")
    startDate.text = fitResult["start_time"].strftime('%a %b %d %H:%M:%S GMT%z %Y')

    statistic = ET.SubElement(generalInformation, "statistic")
    statistic.text = "true"

    timeOverZone = ET.SubElement(generalInformation, "timeOverZone")
    timeOverZone.text = "0"

    timeUnderZone = ET.SubElement(generalInformation, "timeUnderZone")
    timeUnderZone.text = "0"

    # 0-4
    trackProfile = ET.SubElement(generalInformation, "trackProfile")
    trackProfile.text = str(notes["trip_profile"])

    # Training type (short info)
    trainingType = ET.SubElement(generalInformation, "trainingType")
    trainingType.text = "training type"

    # training time [ms]
    trainingTime = ET.SubElement(generalInformation, "trainingTime")
    trainingTime.text = str(fitResult["total_timer_time"]*100)


    # training time uphill [ms]
    #trainingTimeDownhill = ET.SubElement(generalInformation, "trainingTimeDownhill")
    #trainingTimeDownhill.text = ""
    
    # training time downhill [ms]
    #trainingTimeUphill = ET.SubElement(generalInformation, "trainingTimeUphill")
    #trainingTimeUphill.text = ""

    unitId = ET.SubElement(generalInformation, "unitId")
    unitId.text = ""

    # 0-7
    # 0 - sunny
    # 1 - loght cloud
    # 2 - Cloudy
    # 3 - Light rain
    # 4 - Rain
    # 5 - Storm
    # 6 - Snow
    # 7 - fog
    weather = ET.SubElement(generalInformation, "weather")
    weather.text = str(notes["weather"])


    # 0-12
    wind = ET.SubElement(generalInformation, "wind")
    wind.text = str(notes["wind"])

    #zone1Start = ET.SubElement(generalInformation, "zone1Start")
    #zone1Start.text = "15"

    #zone2Start = ET.SubElement(generalInformation, "zone2Start")
    #zone2Start.text = "15"

    #zone3Start = ET.SubElement(generalInformation, "zone3Start")
    #zone3Start.text = "15"

    #zone3End = ET.SubElement(generalInformation, "zone3End")
    #zone3End.text = "0"

    activityStatus = ET.SubElement(generalInformation, "activityStatus")
    activityStatus.text = "none"

    activityTrackerDayComplete = ET.SubElement(generalInformation, "activityTrackerDayComplete")
    activityTrackerDayComplete.text = "false"

    compGUID = ET.SubElement(generalInformation, "compGUID")

    compStartDate = ET.SubElement(generalInformation, "compStartDate")
    compStartDate.text = "0"

    compName = ET.SubElement(generalInformation, "compName")

    compDistance = ET.SubElement(generalInformation, "compDistance")
    compDistance.text = "0"

    compTime = ET.SubElement(generalInformation, "compTime")
    compTime.text = "0"

    compTransitionDuration = ET.SubElement(generalInformation, "compTransitionDuration")
    compTransitionDuration.text = "0"

    sharingInfo = ET.SubElement(generalInformation, "sharingInfo")
    sharingInfo.text = '{"facebookId":"0","komootId":"0","sigmaStatisticsId":"0","stravaId":"0","trainingPeaksId":"0","twitterId":"0","twoPeaksId":"0"}'

    Participant = ET.SubElement(generalInformation, "Participant")

    tree = ET.ElementTree(root)
    file = os.path.join(ACTIVITIES_DIR, "%s.smf" % notes["file_name"])
    tree.write(file, encoding="utf-8", xml_declaration=True)

def saveRunningToSmfFile(fitResult, notes, activityNumber):
    print ("Saving running to smf file ...")
    root = ET.Element("Activity")

    root.set("fileDate", datetime.datetime.now().strftime('%a %b %d %H:%M:%S GMT%z %Y'))
    root.set("revision", "400")
    computer = ET.SubElement(root,"Computer")
    computer.set("unit","user defined")
    computer.set("serial","")
    computer.set("activityType","Running")
    computer.set("dateCode","")

    generalInformation = ET.SubElement(root, "GeneralInformation")
    user = ET.SubElement(generalInformation, "user")
    user.text = "Standard"

    sport = ET.SubElement(generalInformation, "sport")
    sport.text = "running"

    guid = ET.SubElement(generalInformation, "GUID")
    guid.text = "0"

    mdds = ET.SubElement(generalInformation, "modificationDateDeviceSync")
    mdds.text = "0"

    # Altitude uphill [dm]
    altitudeDifferencesDownhill = ET.SubElement(generalInformation, "altitudeDifferencesDownhill")
    altitudeDifferencesDownhill.text = str(fitResult["total_descent"]*1000)

    # Altitude downhill [dm]
    altitudeDifferencesUphill = ET.SubElement(generalInformation, "altitudeDifferencesUphill")
    altitudeDifferencesUphill.text = str(fitResult["total_ascent"]*1000)
    
    # Altitude max
    maximumAltitude = ET.SubElement(generalInformation, "maximumAltitude")
    maximumAltitude.text = str(fitResult["max_altitude"]*1000)

    #Cadence [rpm]
    #averageCadence = ET.SubElement(generalInformation, "averageCadence")
    #averageCadence.text = "1"

    # Heart rate avg
    averageHeartrate = ET.SubElement(generalInformation, "averageHeartrate")
    averageHeartrate.text = str(fitResult["avg_heart_rate"])

    # Hear rate max
    maximumHeartrate = ET.SubElement(generalInformation, "maximumHeartrate")
    maximumHeartrate.text = str(fitResult["max_heart_rate"])
    
    # ?????
    hrMax = ET.SubElement(generalInformation, "hrMax")
    hrMax.text = "300"

    # Incline down [%]
    #averageInclineDownhill = ET.SubElement(generalInformation, "averageInclineDownhill")
    #averageInclineDownhill.text = "2"

    # Incline up [%]
    #averageInclineUphill = ET.SubElement(generalInformation, "averageInclineUphill")
    #averageInclineUphill.text = "3"

    # Incline min [%]
    #maximumInclineDownhill = ET.SubElement(generalInformation, "maximumInclineDownhill")
    #maximumInclineDownhill.text = "44"

    # Incline max [%]
    #maximumInclineUphill = ET.SubElement(generalInformation, "maximumInclineUphill")
    #maximumInclineUphill.text = "55"

    # ?????????
    #averageRiseRateUphill = ET.SubElement(generalInformation, "averageRiseRateUphill")
    #averageRiseRateUphill.text = "4"

    # ???????????
    #averageRiseRateDownhill = ET.SubElement(generalInformation, "averageRiseRateDownhill")
    #averageRiseRateDownhill.text = "5"

    # Speed avg [m/s]
    averageSpeed = ET.SubElement(generalInformation, "averageSpeed")
    averageSpeed.text = str(float (fitResult["avg_speed"]))

    # Speed max [m/s]
    maximumSpeed = ET.SubElement(generalInformation, "maximumSpeed")
    maximumSpeed.text = str(float (fitResult["max_speed"]))

    # Speed uphill [m/s]
    #averageSpeedDownhill = ET.SubElement(generalInformation, "averageSpeedDownhill")
    #averageSpeedDownhill.text = "6"

    # Speed downhill [m/s]
    #averageSpeedUphill = ET.SubElement(generalInformation, "averageSpeedUphill")
    #averageSpeedUphill.text = "7"

    calibration = ET.SubElement(generalInformation, "calibration")
    calibration.text = "false"

    # Calories [kcal]
    calories = ET.SubElement(generalInformation, "calories")
    calories.text = str(fitResult["total_calories"])

    dataType = ET.SubElement(generalInformation, "dataType")
    dataType.text = "memory"

    # Description
    description = ET.SubElement(generalInformation, "description")
    description.text = "description"

    # Trip distance [m]
    distance = ET.SubElement(generalInformation, "distance")
    distance.text = str(float(fitResult["total_distance"]))

    # Distance downhill
    #distanceDownhill = ET.SubElement(generalInformation, "distanceDownhill")
    #distanceDownhill.text = "0"

    # Distance uphill
    #distanceUphill = ET.SubElement(generalInformation, "distanceUphill")
    #distanceUphill.text = "0"

    externalLink = ET.SubElement(generalInformation, "externalLink")
    externalLink.text = "%s/%s"%("https://connect.garmin.com/modern/activity",activityNumber)

    # Linked Track
    linkedRouteId = ET.SubElement(generalInformation, "linkedRouteId")
    linkedRouteId.text = "0"

    logVersion = ET.SubElement(generalInformation, "logVersion")
    logVersion.text = "400"

    manualTemperature = ET.SubElement(generalInformation, "manualTemperature")
    manualTemperature.text = str(notes["temperature"])

    # Cadence max [rpm]
    #maximumCadence = ET.SubElement(generalInformation, "maximumCadence")
    #maximumCadence.text = "0"

    #minimumRiseRate = ET.SubElement(generalInformation, "minimumRiseRate")
    #minimumRiseRate.text = "0"

    #maximumRiseRate = ET.SubElement(generalInformation, "maximumRiseRate")
    #maximumRiseRate.text = "0"

    #minimumTemperature = ET.SubElement(generalInformation, "minimumTemperature")
    #minimumTemperature.text = "400"

    #maximumTemperature = ET.SubElement(generalInformation, "maximumTemperature")
    #maximumTemperature.text = "0"

    name = ET.SubElement(generalInformation, "name")
    name.text = str(notes["file_name"])

    pauseTime = ET.SubElement(generalInformation, "pauseTime")
    pauseTime.text = ""

    # 0-5
    rating = ET.SubElement(generalInformation, "rating")
    rating.text = str(notes["evaluation"])

    # 0-4
    feeling = ET.SubElement(generalInformation, "feeling")
    feeling.text = str(notes["feelings"])


    samplingRate = ET.SubElement(generalInformation, "samplingRate")
    samplingRate.text = ""

    startDate = ET.SubElement(generalInformation, "startDate")
    startDate.text = fitResult["start_time"].strftime('%a %b %d %H:%M:%S GMT%z %Y')

    statistic = ET.SubElement(generalInformation, "statistic")
    statistic.text = "true"

    timeOverZone = ET.SubElement(generalInformation, "timeOverZone")
    timeOverZone.text = "0"

    timeUnderZone = ET.SubElement(generalInformation, "timeUnderZone")
    timeUnderZone.text = "0"

    # 0-4
    trackProfile = ET.SubElement(generalInformation, "trackProfile")
    trackProfile.text = str(notes["trip_profile"])

    # Training type (short info)
    trainingType = ET.SubElement(generalInformation, "trainingType")
    trainingType.text = "training type"

    # training time [ms]
    trainingTime = ET.SubElement(generalInformation, "trainingTime")
    trainingTime.text = str(fitResult["total_timer_time"]*100)


    # training time uphill [ms]
    #trainingTimeDownhill = ET.SubElement(generalInformation, "trainingTimeDownhill")
    #trainingTimeDownhill.text = ""
    
    # training time downhill [ms]
    #trainingTimeUphill = ET.SubElement(generalInformation, "trainingTimeUphill")
    #trainingTimeUphill.text = ""

    unitId = ET.SubElement(generalInformation, "unitId")
    unitId.text = ""

    # 0-7
    # 0 - sunny
    # 1 - loght cloud
    # 2 - Cloudy
    # 3 - Light rain
    # 4 - Rain
    # 5 - Storm
    # 6 - Snow
    # 7 - fog
    weather = ET.SubElement(generalInformation, "weather")
    weather.text = str(notes["weather"])


    # 0-12
    wind = ET.SubElement(generalInformation, "wind")
    wind.text = str(notes["wind"])

    #zone1Start = ET.SubElement(generalInformation, "zone1Start")
    #zone1Start.text = "15"

    #zone2Start = ET.SubElement(generalInformation, "zone2Start")
    #zone2Start.text = "15"

    #zone3Start = ET.SubElement(generalInformation, "zone3Start")
    #zone3Start.text = "15"

    #zone3End = ET.SubElement(generalInformation, "zone3End")
    #zone3End.text = "0"

    activityStatus = ET.SubElement(generalInformation, "activityStatus")
    activityStatus.text = "none"

    activityTrackerDayComplete = ET.SubElement(generalInformation, "activityTrackerDayComplete")
    activityTrackerDayComplete.text = "false"

    compGUID = ET.SubElement(generalInformation, "compGUID")

    compStartDate = ET.SubElement(generalInformation, "compStartDate")
    compStartDate.text = "0"

    compName = ET.SubElement(generalInformation, "compName")

    compDistance = ET.SubElement(generalInformation, "compDistance")
    compDistance.text = "0"

    compTime = ET.SubElement(generalInformation, "compTime")
    compTime.text = "0"

    compTransitionDuration = ET.SubElement(generalInformation, "compTransitionDuration")
    compTransitionDuration.text = "0"

    sharingInfo = ET.SubElement(generalInformation, "sharingInfo")
    sharingInfo.text = '{"facebookId":"0","komootId":"0","sigmaStatisticsId":"0","stravaId":"0","trainingPeaksId":"0","twitterId":"0","twoPeaksId":"0"}'

    Participant = ET.SubElement(generalInformation, "Participant")

    tree = ET.ElementTree(root)
    file = os.path.join(ACTIVITIES_DIR, "%s.smf" % notes["file_name"])
    tree.write(file, encoding="utf-8", xml_declaration=True)

def saveBscCyclingToSmfFile(fitResult, notes, activityNumber):
    print ("Saving running to smf file ...")
    root = ET.Element("Activity")

    root.set("fileDate", datetime.datetime.now().strftime('%a %b %d %H:%M:%S GMT%z %Y'))
    root.set("revision", "400")
    computer = ET.SubElement(root,"Computer")
    computer.set("unit","user defined")
    computer.set("serial","")
    computer.set("activityType","Cycling")
    computer.set("dateCode","")

    generalInformation = ET.SubElement(root, "GeneralInformation")
    user = ET.SubElement(generalInformation, "user")
    user.text = "Standard"

    #sport = ET.SubElement(generalInformation, "sport")
    #sport.text = "running"

    guid = ET.SubElement(generalInformation, "GUID")
    guid.text = "0"

    mdds = ET.SubElement(generalInformation, "modificationDateDeviceSync")
    mdds.text = "0"

    # Altitude uphill [dm]
    altitudeDifferencesDownhill = ET.SubElement(generalInformation, "altitudeDifferencesDownhill")
    altitudeDifferencesDownhill.text = str(fitResult["total_descent"]*1000)

    # Altitude downhill [dm]
    altitudeDifferencesUphill = ET.SubElement(generalInformation, "altitudeDifferencesUphill")
    altitudeDifferencesUphill.text = str(fitResult["total_ascent"]*1000)
    
    # Altitude max
    maximumAltitude = ET.SubElement(generalInformation, "maximumAltitude")
    maximumAltitude.text = str(fitResult["max_altitude"]*1000)

    #Cadence [rpm]
    #averageCadence = ET.SubElement(generalInformation, "averageCadence")
    #averageCadence.text = "1"

    # Heart rate avg
    averageHeartrate = ET.SubElement(generalInformation, "averageHeartrate")
    averageHeartrate.text = str(fitResult["avg_heart_rate"])

    # Hear rate max
    maximumHeartrate = ET.SubElement(generalInformation, "maximumHeartrate")
    maximumHeartrate.text = str(fitResult["max_heart_rate"])
    
    # ?????
    hrMax = ET.SubElement(generalInformation, "hrMax")
    hrMax.text = "300"

    # Incline down [%]
    #averageInclineDownhill = ET.SubElement(generalInformation, "averageInclineDownhill")
    #averageInclineDownhill.text = "2"

    # Incline up [%]
    #averageInclineUphill = ET.SubElement(generalInformation, "averageInclineUphill")
    #averageInclineUphill.text = "3"

    # Incline min [%]
    #maximumInclineDownhill = ET.SubElement(generalInformation, "maximumInclineDownhill")
    #maximumInclineDownhill.text = "44"

    # Incline max [%]
    #maximumInclineUphill = ET.SubElement(generalInformation, "maximumInclineUphill")
    #maximumInclineUphill.text = "55"

    # ?????????
    #averageRiseRateUphill = ET.SubElement(generalInformation, "averageRiseRateUphill")
    #averageRiseRateUphill.text = "4"

    # ???????????
    #averageRiseRateDownhill = ET.SubElement(generalInformation, "averageRiseRateDownhill")
    #averageRiseRateDownhill.text = "5"

    # Speed avg [m/s]
    averageSpeed = ET.SubElement(generalInformation, "averageSpeed")
    averageSpeed.text = str(float (fitResult["avg_speed"]))

    # Speed max [m/s]
    maximumSpeed = ET.SubElement(generalInformation, "maximumSpeed")
    maximumSpeed.text = str(float (fitResult["max_speed"]))

    # Speed uphill [m/s]
    #averageSpeedDownhill = ET.SubElement(generalInformation, "averageSpeedDownhill")
    #averageSpeedDownhill.text = "6"
     
    # Speed downhill [m/s]
    #averageSpeedUphill = ET.SubElement(generalInformation, "averageSpeedUphill")
    #averageSpeedUphill.text = "7"

    calibration = ET.SubElement(generalInformation, "calibration")
    calibration.text = "false"

    # Calories [kcal]
    calories = ET.SubElement(generalInformation, "calories")
    calories.text = str(fitResult["total_calories"])

    dataType = ET.SubElement(generalInformation, "dataType")
    dataType.text = "memory"

    # Description
    description = ET.SubElement(generalInformation, "description")
    description.text = "description"

    # Trip distance [m]
    distance = ET.SubElement(generalInformation, "distance")
    distance.text = str(float(fitResult["total_distance"]))

    # Distance downhill
    #distanceDownhill = ET.SubElement(generalInformation, "distanceDownhill")
    #distanceDownhill.text = "0"

    # Distance uphill
    #distanceUphill = ET.SubElement(generalInformation, "distanceUphill")
    #distanceUphill.text = "0"

    externalLink = ET.SubElement(generalInformation, "externalLink")
    externalLink.text = "%s/%s"%("https://connect.garmin.com/modern/activity",activityNumber)

    # Linked Track
    linkedRouteId = ET.SubElement(generalInformation, "linkedRouteId")
    linkedRouteId.text = "0"

    logVersion = ET.SubElement(generalInformation, "logVersion")
    logVersion.text = "400"

    manualTemperature = ET.SubElement(generalInformation, "manualTemperature")
    manualTemperature.text = str(notes["temperature"])

    # Cadence max [rpm]
    #maximumCadence = ET.SubElement(generalInformation, "maximumCadence")
    #maximumCadence.text = "0"

    #minimumRiseRate = ET.SubElement(generalInformation, "minimumRiseRate")
    #minimumRiseRate.text = "0"

    #maximumRiseRate = ET.SubElement(generalInformation, "maximumRiseRate")
    #maximumRiseRate.text = "0"

    #minimumTemperature = ET.SubElement(generalInformation, "minimumTemperature")
    #minimumTemperature.text = "400"

    #maximumTemperature = ET.SubElement(generalInformation, "maximumTemperature")
    #maximumTemperature.text = "0"

    name = ET.SubElement(generalInformation, "name")
    name.text = str(notes["file_name"])

    pauseTime = ET.SubElement(generalInformation, "pauseTime")
    pauseTime.text = ""

    # 0-5
    rating = ET.SubElement(generalInformation, "rating")
    rating.text = str(notes["evaluation"])

    # 0-4
    feeling = ET.SubElement(generalInformation, "feeling")
    feeling.text = str(notes["feelings"])


    samplingRate = ET.SubElement(generalInformation, "samplingRate")
    samplingRate.text = ""

    startDate = ET.SubElement(generalInformation, "startDate")
    startDate.text = fitResult["start_time"].strftime('%a %b %d %H:%M:%S GMT%z %Y')

    statistic = ET.SubElement(generalInformation, "statistic")
    statistic.text = "true"

    timeOverZone = ET.SubElement(generalInformation, "timeOverZone")
    timeOverZone.text = "0"

    timeUnderZone = ET.SubElement(generalInformation, "timeUnderZone")
    timeUnderZone.text = "0"

    # 0-4
    trackProfile = ET.SubElement(generalInformation, "trackProfile")
    trackProfile.text = str(notes["trip_profile"])

    # Training type (short info)
    trainingType = ET.SubElement(generalInformation, "trainingType")
    trainingType.text = "training type"

    # training time [ms]
    trainingTime = ET.SubElement(generalInformation, "trainingTime")
    trainingTime.text = str(fitResult["total_timer_time"]*100)


    # training time uphill [ms]
    #trainingTimeDownhill = ET.SubElement(generalInformation, "trainingTimeDownhill")
    #trainingTimeDownhill.text = ""
    
    # training time downhill [ms]
    #trainingTimeUphill = ET.SubElement(generalInformation, "trainingTimeUphill")
    #trainingTimeUphill.text = ""

    unitId = ET.SubElement(generalInformation, "unitId")
    unitId.text = ""

    # 0-7
    # 0 - sunny
    # 1 - loght cloud
    # 2 - Cloudy
    # 3 - Light rain
    # 4 - Rain
    # 5 - Storm
    # 6 - Snow
    # 7 - fog
    weather = ET.SubElement(generalInformation, "weather")
    weather.text = str(notes["weather"])


    # 0-12
    wind = ET.SubElement(generalInformation, "wind")
    wind.text = str(notes["wind"])

    #zone1Start = ET.SubElement(generalInformation, "zone1Start")
    #zone1Start.text = "15"

    #zone2Start = ET.SubElement(generalInformation, "zone2Start")
    #zone2Start.text = "15"

    #zone3Start = ET.SubElement(generalInformation, "zone3Start")
    #zone3Start.text = "15"

    #zone3End = ET.SubElement(generalInformation, "zone3End")
    #zone3End.text = "0"

    activityStatus = ET.SubElement(generalInformation, "activityStatus")
    activityStatus.text = "none"

    activityTrackerDayComplete = ET.SubElement(generalInformation, "activityTrackerDayComplete")
    activityTrackerDayComplete.text = "false"

    compGUID = ET.SubElement(generalInformation, "compGUID")

    compStartDate = ET.SubElement(generalInformation, "compStartDate")
    compStartDate.text = "0"

    compName = ET.SubElement(generalInformation, "compName")

    compDistance = ET.SubElement(generalInformation, "compDistance")
    compDistance.text = "0"

    compTime = ET.SubElement(generalInformation, "compTime")
    compTime.text = "0"

    compTransitionDuration = ET.SubElement(generalInformation, "compTransitionDuration")
    compTransitionDuration.text = "0"

    sharingInfo = ET.SubElement(generalInformation, "sharingInfo")
    sharingInfo.text = '{"facebookId":"0","komootId":"0","sigmaStatisticsId":"0","stravaId":"0","trainingPeaksId":"0","twitterId":"0","twoPeaksId":"0"}'

    Participant = ET.SubElement(generalInformation, "Participant")

    tree = ET.ElementTree(root)
    file = os.path.join(ACTIVITIES_DIR, "%s.smf" % notes["file_name"])
    tree.write(file, encoding="utf-8", xml_declaration=True)

def saveGarminCyclingToSmfFile(fitResult, notes, activityNumber):
    print ("Saving running to smf file ...")
    root = ET.Element("Activity")

    root.set("fileDate", datetime.datetime.now().strftime('%a %b %d %H:%M:%S GMT%z %Y'))
    root.set("revision", "400")
    computer = ET.SubElement(root,"Computer")
    computer.set("unit","user defined")
    computer.set("serial","")
    computer.set("activityType","Cycling")
    computer.set("dateCode","")

    generalInformation = ET.SubElement(root, "GeneralInformation")
    user = ET.SubElement(generalInformation, "user")
    user.text = "Standard"

    #sport = ET.SubElement(generalInformation, "sport")
    #sport.text = "running"

    guid = ET.SubElement(generalInformation, "GUID")
    guid.text = "0"

    mdds = ET.SubElement(generalInformation, "modificationDateDeviceSync")
    mdds.text = "0"

    # Altitude uphill [dm]
    altitudeDifferencesDownhill = ET.SubElement(generalInformation, "altitudeDifferencesDownhill")
    altitudeDifferencesDownhill.text = str(fitResult["total_descent"]*1000)

    # Altitude downhill [dm]
    altitudeDifferencesUphill = ET.SubElement(generalInformation, "altitudeDifferencesUphill")
    altitudeDifferencesUphill.text = str(fitResult["total_ascent"]*1000)
    
    # Altitude max
    maximumAltitude = ET.SubElement(generalInformation, "maximumAltitude")
    maximumAltitude.text = str(fitResult["max_altitude"]*1000)

    #Cadence [rpm]
    #averageCadence = ET.SubElement(generalInformation, "averageCadence")
    #averageCadence.text = "1"

    # Heart rate avg
    averageHeartrate = ET.SubElement(generalInformation, "averageHeartrate")
    averageHeartrate.text = str(fitResult["avg_heart_rate"])

    # Hear rate max
    maximumHeartrate = ET.SubElement(generalInformation, "maximumHeartrate")
    maximumHeartrate.text = str(fitResult["max_heart_rate"])
    
    # ?????
    hrMax = ET.SubElement(generalInformation, "hrMax")
    hrMax.text = "300"

    # Incline down [%]
    #averageInclineDownhill = ET.SubElement(generalInformation, "averageInclineDownhill")
    #averageInclineDownhill.text = "2"

    # Incline up [%]
    #averageInclineUphill = ET.SubElement(generalInformation, "averageInclineUphill")
    #averageInclineUphill.text = "3"

    # Incline min [%]
    #maximumInclineDownhill = ET.SubElement(generalInformation, "maximumInclineDownhill")
    #maximumInclineDownhill.text = "44"

    # Incline max [%]
    #maximumInclineUphill = ET.SubElement(generalInformation, "maximumInclineUphill")
    #maximumInclineUphill.text = "55"

    # ?????????
    #averageRiseRateUphill = ET.SubElement(generalInformation, "averageRiseRateUphill")
    #averageRiseRateUphill.text = "4"

    # ???????????
    #averageRiseRateDownhill = ET.SubElement(generalInformation, "averageRiseRateDownhill")
    #averageRiseRateDownhill.text = "5"

    # Speed avg [m/s]
    averageSpeed = ET.SubElement(generalInformation, "averageSpeed")
    averageSpeed.text = str(float (fitResult["avg_speed"]))

    # Speed max [m/s]
    maximumSpeed = ET.SubElement(generalInformation, "maximumSpeed")
    maximumSpeed.text = str(float (fitResult["max_speed"]))

    # Speed uphill [m/s]
    #averageSpeedDownhill = ET.SubElement(generalInformation, "averageSpeedDownhill")
    #averageSpeedDownhill.text = "6"
     
    # Speed downhill [m/s]
    #averageSpeedUphill = ET.SubElement(generalInformation, "averageSpeedUphill")
    #averageSpeedUphill.text = "7"

    calibration = ET.SubElement(generalInformation, "calibration")
    calibration.text = "false"

    # Calories [kcal]
    calories = ET.SubElement(generalInformation, "calories")
    calories.text = str(fitResult["total_calories"])

    dataType = ET.SubElement(generalInformation, "dataType")
    dataType.text = "memory"

    # Description
    description = ET.SubElement(generalInformation, "description")
    description.text = "description"

    # Trip distance [m]
    distance = ET.SubElement(generalInformation, "distance")
    distance.text = str(float(fitResult["total_distance"]))

    # Distance downhill
    #distanceDownhill = ET.SubElement(generalInformation, "distanceDownhill")
    #distanceDownhill.text = "0"

    # Distance uphill
    #distanceUphill = ET.SubElement(generalInformation, "distanceUphill")
    #distanceUphill.text = "0"

    externalLink = ET.SubElement(generalInformation, "externalLink")
    externalLink.text = "%s/%s"%("https://connect.garmin.com/modern/activity",activityNumber)

    # Linked Track
    linkedRouteId = ET.SubElement(generalInformation, "linkedRouteId")
    linkedRouteId.text = "0"

    logVersion = ET.SubElement(generalInformation, "logVersion")
    logVersion.text = "400"

    manualTemperature = ET.SubElement(generalInformation, "manualTemperature")
    manualTemperature.text = str(notes["temperature"])

    # Cadence max [rpm]
    #maximumCadence = ET.SubElement(generalInformation, "maximumCadence")
    #maximumCadence.text = "0"

    #minimumRiseRate = ET.SubElement(generalInformation, "minimumRiseRate")
    #minimumRiseRate.text = "0"

    #maximumRiseRate = ET.SubElement(generalInformation, "maximumRiseRate")
    #maximumRiseRate.text = "0"

    #minimumTemperature = ET.SubElement(generalInformation, "minimumTemperature")
    #minimumTemperature.text = "400"

    #maximumTemperature = ET.SubElement(generalInformation, "maximumTemperature")
    #maximumTemperature.text = "0"

    name = ET.SubElement(generalInformation, "name")
    name.text = str(notes["file_name"])

    pauseTime = ET.SubElement(generalInformation, "pauseTime")
    pauseTime.text = ""

    # 0-5
    rating = ET.SubElement(generalInformation, "rating")
    rating.text = str(notes["evaluation"])

    # 0-4
    feeling = ET.SubElement(generalInformation, "feeling")
    feeling.text = str(notes["feelings"])


    samplingRate = ET.SubElement(generalInformation, "samplingRate")
    samplingRate.text = ""

    startDate = ET.SubElement(generalInformation, "startDate")
    startDate.text = fitResult["start_time"].strftime('%a %b %d %H:%M:%S GMT%z %Y')

    statistic = ET.SubElement(generalInformation, "statistic")
    statistic.text = "true"

    timeOverZone = ET.SubElement(generalInformation, "timeOverZone")
    timeOverZone.text = "0"

    timeUnderZone = ET.SubElement(generalInformation, "timeUnderZone")
    timeUnderZone.text = "0"

    # 0-4
    trackProfile = ET.SubElement(generalInformation, "trackProfile")
    trackProfile.text = str(notes["trip_profile"])

    # Training type (short info)
    trainingType = ET.SubElement(generalInformation, "trainingType")
    trainingType.text = "training type"

    # training time [ms]
    trainingTime = ET.SubElement(generalInformation, "trainingTime")
    trainingTime.text = str(fitResult["total_timer_time"]*100)


    # training time uphill [ms]
    #trainingTimeDownhill = ET.SubElement(generalInformation, "trainingTimeDownhill")
    #trainingTimeDownhill.text = ""

    # training time downhill [ms]
    #trainingTimeUphill = ET.SubElement(generalInformation, "trainingTimeUphill")
    #trainingTimeUphill.text = ""

    unitId = ET.SubElement(generalInformation, "unitId")
    unitId.text = ""

    # 0-7
    # 0 - sunny
    # 1 - loght cloud
    # 2 - Cloudy
    # 3 - Light rain
    # 4 - Rain
    # 5 - Storm
    # 6 - Snow
    # 7 - fog
    weather = ET.SubElement(generalInformation, "weather")
    weather.text = str(notes["weather"])


    # 0-12
    wind = ET.SubElement(generalInformation, "wind")
    wind.text = str(notes["wind"])

    #zone1Start = ET.SubElement(generalInformation, "zone1Start")
    #zone1Start.text = "15"

    #zone2Start = ET.SubElement(generalInformation, "zone2Start")
    #zone2Start.text = "15"

    #zone3Start = ET.SubElement(generalInformation, "zone3Start")
    #zone3Start.text = "15"

    #zone3End = ET.SubElement(generalInformation, "zone3End")
    #zone3End.text = "0"

    activityStatus = ET.SubElement(generalInformation, "activityStatus")
    activityStatus.text = "none"

    activityTrackerDayComplete = ET.SubElement(generalInformation, "activityTrackerDayComplete")
    activityTrackerDayComplete.text = "false"

    compGUID = ET.SubElement(generalInformation, "compGUID")

    compStartDate = ET.SubElement(generalInformation, "compStartDate")
    compStartDate.text = "0"

    compName = ET.SubElement(generalInformation, "compName")

    compDistance = ET.SubElement(generalInformation, "compDistance")
    compDistance.text = "0"

    compTime = ET.SubElement(generalInformation, "compTime")
    compTime.text = "0"

    compTransitionDuration = ET.SubElement(generalInformation, "compTransitionDuration")
    compTransitionDuration.text = "0"

    sharingInfo = ET.SubElement(generalInformation, "sharingInfo")
    sharingInfo.text = '{"facebookId":"0","komootId":"0","sigmaStatisticsId":"0","stravaId":"0","trainingPeaksId":"0","twitterId":"0","twoPeaksId":"0"}'

    Participant = ET.SubElement(generalInformation, "Participant")

    tree = ET.ElementTree(root)
    file = os.path.join(ACTIVITIES_DIR, "%s.smf" % notes["file_name"])
    tree.write(file, encoding="utf-8", xml_declaration=True)

def notes(
    activity,
    activity_id,
    activity_type,
    fit_result,
    weather_data,
    activity_date,
    allow_missing_temperature=False,
    automatic=True,
):
    activity_name = activity.get("activityName") or activity_type.title()
    fit_temperature = fit_result.get("avg_temperature")
    temperature_celsius = _find_weather_value(weather_data, {"temperaturecelsius"})
    temperature_fahrenheit = _find_weather_value(
        weather_data,
        {"temperature", "airtemperature", "temp"},
    )
    if fit_temperature is not None:
        temperature = float(fit_temperature)
    elif temperature_celsius is not None:
        temperature = float(temperature_celsius)
    elif temperature_fahrenheit is not None:
        temperature = _garmin_temperature_celsius(temperature_fahrenheit)
    else:
        temperature = fit_result.get("avg_temperature")
    if temperature is None:
        temperature = ""

    wind_speed_mph = _find_weather_value(weather_data, {"windspeed"})
    wind_speed_mps = _garmin_wind_speed_mps(wind_speed_mph)
    note = {
        "file_name": _safe_activity_name(
            activity_name, activity_id, activity_date
        ),
        "temperature": temperature,
        "weather": _sigma_weather_code(weather_data),
        "wind": _beaufort_code(wind_speed_mps),
        "weather_description": _weather_description(weather_data) or "",
        "wind_speed_mph": wind_speed_mph if wind_speed_mph is not None else "",
    }

    note["trip_profile"] = _trip_profile_from_elevation(fit_result)

    note["evaluation"] = (
        _evaluation_from_activity(fit_result, activity_type)
        if automatic
        else ""
    )

    return note

def _get_cycling_running_activities(garmin, start_date):
    activities_by_id = {}
    page_size = 20
    start = 0
    while True:
        page = garmin.get_activities(start, page_size)
        if isinstance(page, dict):
            page = page.get("activityList", [])
        if not page:
            break

        reached_date_boundary = False
        for activity in page:
            activity_id = str(activity.get("activityId", ""))
            if not activity_id or _activity_type(activity) not in {
                "cycling",
                "running",
            }:
                continue
            try:
                activity_date = _activity_date(activity)
            except ValueError:
                continue

            if activity_date < start_date.isoformat():
                reached_date_boundary = True
                continue
            if not _activity_fit_is_cached(activity):
                activities_by_id[activity_id] = activity

        if reached_date_boundary or len(page) < page_size:
            break
        start += page_size

    return sorted(
        activities_by_id.values(),
        key=lambda activity: activity.get("startTimeLocal", ""),
    )


def _prompt_start_date():
    while True:
        value = input("Find activities from date (YYYY-MM-DD): ").strip()
        try:
            return datetime.date.fromisoformat(value)
        except ValueError:
            print("Enter a valid date in YYYY-MM-DD format.")


def _show_activity_list(activities):
    print("Cycling and running activities (oldest first):")
    for index, activity in enumerate(activities, start=1):
        distance = activity.get("distance")
        distance_km = float(distance) / 1000 if distance is not None else None
        duration = activity.get("duration")
        duration_hms = (
            konwertujNaFormatCzasu(float(duration))
            if duration is not None
            else "N/A"
        )
        print(
            "%d. %s | %s | %s | %s km | %s"
            % (
                index,
                _activity_type(activity),
                activity.get("activityName"),
                activity.get("startTimeLocal"),
                "%.2f" % distance_km if distance_km is not None else "N/A",
                duration_hms,
            )
        )


def _selected_indices(selection, item_count):
    selection = selection.strip().lower()
    if not selection or selection == "all":
        return list(range(item_count))

    selected = set()
    for part in selection.split(","):
        part = part.strip()
        range_match = re.fullmatch(r"(\d+)\s*-\s*(\d+)", part)
        if range_match:
            first, last = map(int, range_match.groups())
            if first > last:
                raise ValueError("Range must be in ascending order.")
            selected.update(range(first, last + 1))
            continue

        if not part.isdigit():
            raise ValueError("Use numbers, comma-separated numbers, or ranges.")
        selected.add(int(part))

    if not selected or min(selected) < 1 or max(selected) > item_count:
        raise ValueError("Choose numbers from the displayed list.")
    return [index - 1 for index in sorted(selected)]


def _convert_activity(garmin, selected_activity, automatic=True):
    activity_number = str(selected_activity["activityId"])
    activity_date = _activity_date(selected_activity)
    activity_details = garmin.get_activity(activity_number)
    activity_type = (
        _activity_type(activity_details) or _activity_type(selected_activity)
    )
    if activity_type not in {"cycling", "running"}:
        raise ValueError(
            "The selected Garmin activity is not cycling or running."
        )

    weather_data = garmin.get_activity_weather(activity_number)
    activity_name = (
        (activity_details or {}).get("activityName")
        or selected_activity.get("activityName")
        or activity_type.title()
    )
    fit_path = _download_activity_fit(
        garmin, activity_number, activity_date, activity_name
    )
    fit_result = readFitFile(fit_path)
    _apply_garmin_elevation_stats(fit_result, selected_activity)
    _complete_activity_conversion(
        activity_details or selected_activity,
        activity_number,
        activity_type,
        fit_result,
        weather_data,
        activity_date,
        gpx_downloader=garmin,
        automatic=automatic,
    )


def _complete_activity_conversion(
    activity,
    activity_id,
    activity_type,
    fit_result,
    weather_data,
    activity_date,
    gpx_downloader=None,
    automatic=True,
):
    activity_name = (
        activity.get("activityName")
        or fit_result.get("activity_name")
        or activity_type.title()
    )
    output_name = _safe_activity_name(activity_name, activity_id, activity_date)
    if gpx_downloader is not None:
        _download_activity_gpx(gpx_downloader, activity_id, output_name)

    note = notes(
        activity,
        activity_id,
        activity_type,
        fit_result,
        weather_data,
        activity_date,
        allow_missing_temperature=gpx_downloader is None,
        automatic=automatic,
    )
    if automatic:
        note["feelings"] = "3"
    showSmfInputData(fit_result, note, activity_type, activity_id)
    if note["temperature"] == "":
        note["temperature"] = _prompt_temperature()
    if not automatic:
        note["feelings"] = input("Feelings [0-4]: ").strip()
        note["evaluation"] = input("Evaluation [0-5]: ").strip()

    if activity_type == "running":
        saveRunningToSmfFile(fit_result, note, activity_id)
    else:
        saveGarminCyclingToSmfFile(fit_result, note, activity_id)


def _find_fit_files(directory):
    if os.path.isfile(directory):
        if not directory.lower().endswith(".fit"):
            raise ValueError("Offline input file must have a .fit extension: %s" % directory)
        return [directory]

    if not os.path.isdir(directory):
        raise FileNotFoundError("FIT file or search directory does not exist: %s" % directory)

    fit_files = []
    for current_directory, directory_names, file_names in os.walk(directory):
        directory_names[:] = sorted(
            name for name in directory_names
            if name not in {".git", ".venv", "__pycache__"}
        )
        for file_name in file_names:
            if file_name.lower().endswith(".fit"):
                fit_files.append(
                    os.path.join(current_directory, file_name)
                )
    return sorted(fit_files)


def _offline_activity_details(fit_path, fit_result):
    start_time = fit_result.get("start_time")
    if isinstance(start_time, datetime.datetime):
        activity_date = start_time.date().isoformat()
    elif isinstance(start_time, datetime.date):
        activity_date = start_time.isoformat()
    else:
        date_match = re.search(r"\d{4}-\d{2}-\d{2}", os.path.basename(fit_path))
        if not date_match:
            raise ValueError(
                "The FIT file does not contain a start date and its filename "
                "does not include one."
            )
        activity_date = date_match.group(0)

    fit_path_stem = os.path.splitext(os.path.basename(fit_path))[0]
    activity_id_match = re.search(r"(?:^|_)(\d+)(?:_|$)", fit_path_stem)
    activity_id = activity_id_match.group(1) if activity_id_match else ""
    fallback_name = re.sub(
        r"_ACTIVITY$", "", fit_path_stem, flags=re.IGNORECASE
    )
    fallback_name = re.sub(r"^\d{4}-\d{2}-\d{2}_", "", fallback_name)
    fallback_name = re.sub(r"_\d{4}-\d{2}-\d{2}", "", fallback_name)
    if activity_id:
        fallback_name = re.sub(
            r"(?:^|_)%s$" % re.escape(activity_id),
            "",
            fallback_name,
        )
    activity_name = fit_result.get("activity_name") or fallback_name or "activity"

    activity_type = _activity_type(fit_result)
    if activity_type is None:
        normalized_filename = fit_path_stem.lower()
        if "run" in normalized_filename:
            activity_type = "running"
        elif "cycl" in normalized_filename or "bike" in normalized_filename:
            activity_type = "cycling"
    if activity_type is None:
        selection = input(
            "FIT activity type is not identifiable. Enter c for cycling, "
            "r for running: "
        ).strip().lower()
        if selection in {"c", "cycling"}:
            activity_type = "cycling"
        elif selection in {"r", "running"}:
            activity_type = "running"
        else:
            raise ValueError("Choose c/cycling or r/running for the FIT file.")

    return {
        "activityName": activity_name,
        "activityId": activity_id,
        "activity_date": activity_date,
        "activity_type": activity_type,
    }


def _convert_offline_fit(fit_path, automatic=True):
    fit_result = readFitFile(fit_path)
    activity = _offline_activity_details(fit_path, fit_result)
    _complete_activity_conversion(
        activity,
        activity["activityId"],
        activity["activity_type"],
        fit_result,
        {},
        activity["activity_date"],
        automatic=automatic,
    )


def _run_offline(directory, automatic=False):
    processed_files = set()
    while True:
        fit_files = [
            path for path in _find_fit_files(directory)
            if path not in processed_files
        ]
        if not fit_files:
            print("No more FIT files to review.")
            return

        selected_fit = None
        if automatic:
            print("FIT files to convert:")
            for index, fit_path in enumerate(fit_files, start=1):
                print("%d. %s" % (index, fit_path))
            confirmation = input(
                "FIT files to convert [Enter/all=all, e.g. 1,3 or 1-5, q=quit]: "
            ).strip().lower()
            if confirmation == "q":
                return
            try:
                selected_indices = _selected_indices(confirmation, len(fit_files))
            except ValueError as error:
                print(error)
                continue
            for index in selected_indices:
                fit_path = fit_files[index]
                processed_files.add(fit_path)
                _convert_offline_fit(fit_path, automatic=True)
            return

        for index, fit_path in enumerate(fit_files, start=1):
            print("%d. %s" % (index, fit_path))
            confirmation = input(
                "Is this the activity to convert? [y/N/q]: "
            ).strip().lower()
            processed_files.add(fit_path)
            if confirmation == "q":
                return
            if confirmation in {"y", "yes", "t", "tak"}:
                selected_fit = fit_path
                break

        if selected_fit is None:
            print("No FIT file was selected.")
            return

        _convert_offline_fit(selected_fit, automatic=False)


def main(argv=None):
    os.makedirs(ACTIVITIES_DIR, exist_ok=True)
    parser = argparse.ArgumentParser(description="Convert Garmin activities to Sigma SMF.")
    parser.add_argument(
        "--offline",
        nargs="?",
        const=ACTIVITIES_DIR,
        metavar="DIRECTORY",
        help="search for FIT files in DIRECTORY (default: activities directory) without Garmin Connect",
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="convert all listed activities after pressing Enter",
    )
    args = parser.parse_args(argv)

    if args.offline is not None:
        _run_offline(
            os.path.abspath(os.path.expanduser(args.offline)),
            automatic=args.auto,
        )
        return

    garmin = Garmin()
    garmin.login(TOKEN_DIR)

    start_date = _prompt_start_date()
    activities = _get_cycling_running_activities(garmin, start_date)
    if not activities:
        print("No uncached cycling or running activities found from that date.")
        return

    while True:
        if not activities:
            print("No more uncached activities from that date.")
            return

        _show_activity_list(activities)
        if args.auto:
            confirmation = input(
                "Activities to convert [Enter/all=all, e.g. 1,3 or 1-5, q=quit]: "
            ).strip().lower()
            if confirmation == "q":
                return
            try:
                selected_indices = _selected_indices(confirmation, len(activities))
            except ValueError as error:
                print(error)
                continue
            for index in selected_indices:
                selected_activity = activities[index]
                _convert_activity(garmin, selected_activity, automatic=True)
            return

        selection = input("Activity index to convert (or q to quit): ").strip().lower()
        if selection == "q":
            return

        try:
            index = int(selection)
        except ValueError:
            print("Enter one activity index, or q to quit.")
            continue

        if index < 1 or index > len(activities):
            print("Choose one index from the displayed activity list.")
            continue

        selected_activity = activities.pop(index - 1)
        _convert_activity(garmin, selected_activity, automatic=False)

if __name__ == '__main__':
    main()
