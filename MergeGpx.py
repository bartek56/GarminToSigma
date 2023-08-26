import gpxpy
import gpxpy.gpx
import os
import argparse
from gpxpy.gpx import GPXTrackPoint, GPX

class Track():
    def __init__(self, name:str, type:str, segments:list):
        self.name = name
        self.type = type
        self.segments = segments

class MergeGPX():
    def __init__(self, skipPoints=1, clearExtension=True):
        self.skipPoints = skipPoints
        self.clearExtension = clearExtension

    def mergeByTracks(self, GpxFiles:list, resultName):
        listOfGpxFiles = GpxFiles

        listTracks = []
        for gpx in listOfGpxFiles[1:]:
            tracks = self.loadTracksFromGpx(gpx)
            if len(tracks) == 0:
                print("file", gpx, "doesn't contain tracks. This file was skipped")
                continue
            listTracks.extend(tracks)

        gpxResult = self.mergeTracksWithFirst(listOfGpxFiles[0], listTracks)

        self.save(gpxResult.to_xml(), resultName)

    def loadTracksFromGpx(self, fileName):
        trackName = ""
        trackType = ""
        trackPoints = []

        gpx_file = open(fileName, 'r')
        gpx = gpxpy.parse(gpx_file)
        gpx_file.close()
        self.clearExtensionsFromGpx(gpx)

        listOfTracks = []
        for track in gpx.tracks:
            trackName = track.name
            trackType = track.type
            listOfSegments = []
            for segment in track.segments:
                listOfSegments.append(segment.points)

            listOfTracks.append(Track(trackName, trackType, listOfSegments))

        return listOfTracks

    def mergeTracksWithFirst(self, fileOfFirstTrack, otherTracks:list[Track]):
        gpx_file = open(fileOfFirstTrack, 'r')
        gpx = gpxpy.parse(gpx_file)
        gpx_file.close()
        self.clearExtensionsFromGpx(gpx)

        for track in otherTracks:
            newTrack = gpxpy.gpx.GPXTrack()
            newTrack.name = track.name
            newTrack.type = track.type
            for segment in track.segments:
                newSegment = gpxpy.gpx.GPXTrackSegment()
                newTrack.segments.append(newSegment)
                i = 0
                for point in segment:
                    if i%self.skipPoints == 0:
                        newSegment.points.append(point)
                        i = 0
                    i+=1
            gpx.tracks.append(newTrack)

        return gpx

    def loadSegmentsFromGpx(self, fileName):
        gpx_file = open(fileName, 'r')
        gpx = gpxpy.parse(gpx_file)
        gpx_file.close()
        self.clearExtensionsFromGpx(gpx)

        if len(gpx.tracks) > 1:
            print("file uses for merging:", fileName, "contains more then one track !!!")
            print("Segments will be taken from all tracks and marged to track from first file")

        listOfSegments = []
        for track in gpx.tracks:
            for segment in track.segments:
                listOfSegments.append(segment.points)
        return listOfSegments

    def mergeBySegments(self, GpxFiles:list, resultName):
        listOfGpxFiles = GpxFiles

        listSegments = []
        for gpx in listOfGpxFiles[1:]:
            segments = self.loadSegmentsFromGpx(gpx)
            if len(segments) == 0:
                print("file", gpx, "doesn't contain segments. This file was skipped")
                continue
            listSegments.extend(segments)

        gpxResult = self.mergeSegmentsWithFirst(listOfGpxFiles[0], listSegments)

        self.save(gpxResult.to_xml(), resultName)

    def mergeSegmentsWithFirst(self, fileOfFirstTrack, otherSegments:list):
        gpx_file = open(fileOfFirstTrack, 'r')
        gpx = gpxpy.parse(gpx_file)
        gpx_file.close()
        self.clearExtensionsFromGpx(gpx)
        if len(gpx.tracks) > 1:
            print("First file contains more then one track. I do not know how to merge it")
            exit()

        for pointsOfSegment in otherSegments:
            newSegment = gpxpy.gpx.GPXTrackSegment()
            i = 0
            for point in pointsOfSegment:
                if i%self.skipPoints == 0:
                    newSegment.points.append(point)
                    i = 0
                i+=1

            gpx.tracks[0].segments.append(newSegment)
        return gpx

    def mergeByPoints(self, GpxFiles:list, resultName):
        listOfGpxFiles = GpxFiles

        listPoints = []
        for gpx in listOfGpxFiles[1:]:
            points = self.loadPointsFromGpx(gpx)
            if len(points) == 0:
                print("file", gpx, "doesn't contain points. This file was skipped")
                continue
            listPoints.extend(points)

        gpxResult = self.mergePointsWithFirst(listOfGpxFiles[0], listPoints)

        self.save(gpxResult.to_xml(), resultName)

    def mergePointsWithFirst(self, fileOfFirstTrack, otherPoints:list[GPXTrackPoint]):
        gpx_file = open(fileOfFirstTrack, 'r')
        gpx = gpxpy.parse(gpx_file)
        gpx_file.close()
        self.clearExtensionsFromGpx(gpx)
        if len(gpx.tracks) > 1:
            print("First file contains more then one track. I do not know how to merge it")
            exit()
        if len(gpx.tracks[0].segments) > 1:
            print("First file contains more then one segment. I do not know how to merge it")
            exit()
        i = 0
        for point in otherPoints:
            if i%self.skipPoints == 0:
                gpx.tracks[0].segments[0].points.append(point)
                i = 0
            i+=1
        return gpx

    def loadPointsFromGpx(self, fileName):
        gpx_file = open(fileName, 'r')
        gpx = gpxpy.parse(gpx_file)
        gpx_file.close()

        self.clearExtensionsFromGpx(gpx)

        if len(gpx.tracks) > 1:
            print("file used for merging:", fileName, "contains more then one track !!!")
            print("Points will be taken from all tracks for marging without splitting to tracks")

        listOfPoints = []
        for track in gpx.tracks:
            if len(track.segments) > 1:
                print("file used for merging:", fileName, "contains more then one segment !!!")
                print("Points will be taken from all segments for marging without splitting to segments")
            for segment in track.segments:
                listOfPoints.extend(segment.points)
        return listOfPoints

    def clearExtensionsFromGpx(self, gpx:GPX):
        if self.clearExtension:
            for track in gpx.tracks:
                for segment in track.segments:
                    for point in segment.points:
                        point.extensions.clear()

    def save(self, fileContent, fileName):
        with open(fileName, 'w') as f:
            f.write(fileContent)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog = "MergeGpx", description="script to merge or editing gpx files")

    parser.add_argument("-s", "--skip", help="how much points to skip for optimization. 1 - without skipping, 2 - every second etc. Default is 1", nargs='?', dest='skippingNumber', default='1')
    parser.add_argument("-o", "--output", help="gpx output filename")
    parser.add_argument("-c","--clear", action='store_true', help="clear extension data")
    parser.add_argument('-t','--type',
                       action='store',
                       choices=['tracks', 'segments', 'points'],
                       dest='typeOfMerge',
                       help='Type of merge: tracks - tracks will be separated on the one gpx [default] \
                             segments - one track, segments will be join - good option to merge the same day of activity\
                             points - merge points to one segment - nobody will know, that you merged gpxs', default='tracks')

    parser.add_argument("path", help="directory to gpx files or path to gpx file for editing", nargs='?', default=os.getcwd())

    args = parser.parse_args()
    path = args.path
    skippingNumber = int(args.skippingNumber)
    outputFileName=args.output
    clearExtension = args.clear
    typeOfMerge = args.typeOfMerge

    if os.path.isfile(path):
        print("editing gpx file is not supported")
        exit()

    if not os.path.isdir(path):
        print("dir for gpx files not exist")
        exit()
    if not ".gpx" in outputFileName:
        print("output filename has to have gpx extension")
        exit()
    if os.path.isfile(outputFileName):
        print("output filename already exist")
        exit()

    list = os.listdir(path)
    if len(list) < 2:
        print("too less files for merge")
        exit()

    listOfGpx = []
    for x in list:
        if ".gpx" in x:
            listOfGpx.append(os.path.join(path,x))
    listOfGpx.sort()

    mergeGpx = MergeGPX(skipPoints=skippingNumber, clearExtension=clearExtension)
    if typeOfMerge == "tracks":
        mergeGpx.mergeByTracks(listOfGpx, outputFileName)
    elif typeOfMerge == "segments":
        mergeGpx.mergeBySegments(listOfGpx, outputFileName)
    elif typeOfMerge == "points":
        mergeGpx.mergeByPoints(listOfGpx, outputFileName)
