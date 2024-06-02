import fitdecode
import xml.etree.ElementTree as ET
import datetime
import time
import csv
import zipfile
import os

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

def showResultsFromFit(data):
    for k, v in data.items():
        if k == "total_timer_time":
            print(k, v,"s   ", konwertujNaFormatCzasu(v))
        elif k == "total_distance":
            print(k, v, 'm',)
        elif k == "avg_speed":
            print(k, v,  konwerujMpSOnKmPh(v))
        elif k == "max_speed":
            print(k, v, konwerujMpSOnKmPh(v))
        else:    
            print (k, v)

def readFitFile(filename):
    print ("Reading fit file ...")
    result = {"max_altitude":1}
    result["min_altitude"] = 9999
    isGarmin5 = False
    isGarmin3 = False
    #garmin_product 4427 Garmin5
    #garmin_product 2989 Garmin3

    with fitdecode.FitReader(filename) as fit:
        for frame in fit:
            if isinstance(frame, fitdecode.FitDataMessage):
                for x in range(len(frame.fields)):
                    if isGarmin3 == False and isGarmin5 == False:
                        if "garmin_product" in frame.fields[x].name:
                            if str(frame.fields[x].value).isdigit():
                                #print(frame.fields[x].value)
                                if int(frame.fields[x].value) > 3500:
                                    isGarmin5 = True
                                    print("Garmin5")
                                else:
                                    isGarmin3 = True
                                    print("Garmin3")
                    if isGarmin5:
                        if "min_altitude" in frame.fields[x].name:
                            if(frame.fields[x].value is not None):
                                if result["min_altitude"] > frame.fields[x].value:
                                    result["min_altitude"] = frame.fields[x].value
                        if "max_altitude" in frame.fields[x].name:
                            if(frame.fields[x].value is not None):
                                if result["max_altitude"] < frame.fields[x].value:
                                    result["max_altitude"] = frame.fields[x].value
                    if isGarmin3:
                        if "altitude" in frame.fields[x].name:
                            if(result["max_altitude"] < frame.fields[x].value):
                                result["max_altitude"] = frame.fields[x].value
                            if(result["min_altitude"] > frame.fields[x].value):
                                result["min_altitude"] = frame.fields[x].value
                    if "avg_heart_rate" in frame.fields[x].name:
                        result["avg_heart_rate"] = frame.fields[x].value
                    if "max_heart_rate" in frame.fields[x].name:
                        result["max_heart_rate"] = frame.fields[x].value
                    if "total_timer_time" in frame.fields[x].name:
                        result["total_timer_time"] = frame.fields[x].value
                    if "total_ascent" in frame.fields[x].name:
                        result["total_ascent"] = frame.fields[x].value
                    if "total_descent" in frame.fields[x].name:
                        result["total_descent"] = frame.fields[x].value
                    if "max_speed" in frame.fields[x].name:
                        if frame.fields[x].value is not None:
                            result["max_speed"] = frame.fields[x].value
                    if "avg_speed" in frame.fields[x].name:
                        if frame.fields[x].value is not None:
                           result["avg_speed"] = frame.fields[x].value
                    if "total_calories" in frame.fields[x].name:
                        result["total_calories"] = frame.fields[x].value
                    if "start_time" in frame.fields[x].name:
                        result["start_time"] = frame.fields[x].value
                    if "total_timer_time" in frame.fields[x].name:
                        result["total_timer_time"] = frame.fields[x].value
                    if "total_distance" in frame.fields[x].name:
                        result["total_distance"] = frame.fields[x].value

    showResultsFromFit(result)
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
    file = "%s.smf"%(notes["file_name"])
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
    file = "%s.smf"%(notes["file_name"])
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
    file = "%s.smf"%(notes["file_name"])
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
    file = "%s.smf"%(notes["file_name"])
    tree.write(file, encoding="utf-8", xml_declaration=True)

def extractZip(fileName):
    print ("Extracting ...")
    file = "%s.%s"%(fileName,"zip")
    with zipfile.ZipFile(file, 'r') as zip_ref:
        zip_ref.extractall()

def notes():
    note = {"weather":1}
    note["file_name"] = input("Result file Name: ")
    note["weather"] = input("Weather [0-7]: \n \
        0 - sunny \n \
        1 - light cloud \n \
        2 - Cloudy \n \
        3 - Light rain \n \
        4 - Rain \n \
        5 - Storm \n \
        6 - Snow \n \
        7 - Fog \n -> ")


    note["wind"] = input("wind [0-12]: \n \
        0 - 0 Bft Calm \n \
        1 - 1 Bft Light air \n \
        2 - 2 Bft Light breeze \n \
        3 - 3 Bft Gentle breeze \n \
        4 - 4 Bft Moderate breeze \n \
        5 - 5 Bft Fresh breeze \n \
        6 - 6 Bft Strong breeze \n \
        7 - 7 Bft Moderate gale \n \
        8 - 8 Bft Fresh gale \n \
        9 - 9 Bft Strong gale \n \
        10 - 10 Bft whole gale \n \
        11 - 11 Bft Violent storm \n \
        12 - 12 Bft Hurricane \n -> ")

    note["trip_profile"] = input("Trip Profile [0-7]: \n \
        0 - flat \n \
        1 - slightly undulating \n \
        2 - undulating \n \
        3 - mountainous \n \
        4 - steep \n -> ")
    
    note["feelings"] = input("Feelings [0-4]: \n \
        4 - very happy \n \
        3 - happy \n \
        2 - normal \n \
        1 - sad \n \
        0 - very sad  \n -> ")

    note["evaluation"] = input("Evaluation [0-5]: ")    

    return note

def main():

    computerBike = input("Computer Bike [1-2]: \n \
        1 - BC 16.16 \n \
        2 - BC 12.12 \n \
        3 - cycling \n \
        4 - BSC \n \
        5 - running \n \
        -> ")

    activityNumber = "0"
    for file in os.listdir("./"):
        if file.endswith(".zip"):
            activityNumber = file
            activityNumber = activityNumber.strip(".zip")


    confirmActivityNumber = input("Whether the activity number is: " + activityNumber + " [y/n]")
    if confirmActivityNumber == 'y':
        print("start reading the file")
    elif confirmActivityNumber == 'n':
        activityNumber = input("Activity number: ")
    else:
        print("error")
        return

    if activityNumber == 0:
        print("error")
        return

    extractZip(activityNumber)
    fitResult = readFitFile("%s_ACTIVITY.fit"%(activityNumber))
    
    # BC12 or BC16
    if computerBike == "1" or computerBike == "2":
        csvResult={"trip_distance":50.0}
        if computerBike == '1':
            csvResult = readCSVFileBC16("sigmaBC16")
        elif computerBike == '2':
            csvResult = readCSVFileBC12("sigmaBC12")

        note = notes()
        saveToSmfFile(computerBike, fitResult, csvResult, note, activityNumber)
    # garmin cycling
    elif computerBike == "3":
        note = notes()
        note["temperature"] = input("Temperature: ")
        saveGarminCyclingToSmfFile(fitResult, note, activityNumber)
    # BSC
    elif computerBike == "4":
        note = notes()
        note["temperature"] = input("Temperature: ")
        saveBscCyclingToSmfFile(fitResult, note, activityNumber)    
    # running
    if computerBike == "5":
        note = notes()
        note["temperature"] = input("Temperature: ")
        saveRunningToSmfFile(fitResult, note, activityNumber)
    
    activityFile = "%s_ACTIVITY.%s"%(activityNumber,"fit")
    os.remove(activityFile)
    activityArchive = "%s.%s"%(activityNumber,"zip")
    os.remove(activityArchive)


if __name__ == '__main__':
    main()
