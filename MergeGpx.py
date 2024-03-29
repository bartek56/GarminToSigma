from abc import abstractmethod
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

    def merge(self, gpxFiles, resultFilename):
        listOfGpxFiles = gpxFiles

        listOfData = []
        for gpx in listOfGpxFiles[1:]:
            tracks = self.load(gpx)
            if len(tracks) == 0:
                print("file", gpx, "doesn't contain tracks. This file was skipped")
                continue
            listOfData.extend(tracks)

        gpxResult = self.mergeWithFirst(listOfGpxFiles[0], listOfData)

        self.save(gpxResult.to_xml(), resultFilename)

    @abstractmethod
    def load(self, fileName):
        pass

    @abstractmethod
    def mergeWithFirst(self, fileOfFirst, otherFiles):
        pass

    def editGpx(self, gpxFile, resultFileName):
        gpx = self.openGpx(gpxFile)
        self.save(gpx.to_xml(), resultFileName)

    def settings(self, skipPoints:int, clearExtension:bool):
        self.clearExtension = clearExtension
        self.skipPoints = skipPoints

    def clearExtensionsFromGpx(self, gpx:GPX):
        for track in gpx.tracks:
            for segment in track.segments:
                for point in segment.points:
                    point.extensions.clear()

    def skipPointsFromTrack(self, gpx):
        for track in gpx.tracks:
            for segment in track.segments:
                newListOfPoints = []
                i = 0
                for point in segment.points:
                    if i%self.skipPoints==0:
                        newListOfPoints.append(point)
                        i=0
                    i+=1
                segment.points = newListOfPoints

    def openGpx(self, file):
        gpx_file = open(file, 'r')
        gpx = gpxpy.parse(gpx_file)
        gpx_file.close()
        if self.clearExtension:
            self.clearExtensionsFromGpx(gpx)
        if self.skipPoints > 1:
            self.skipPointsFromTrack(gpx)
        return gpx

    def save(self, fileContent, fileName):
        with open(fileName, 'w') as f:
            f.write(fileContent)

class MergeGPXByTracks(MergeGPX):
    def __init__(self, skipPoints:int=1, clearExtension:bool=True):
        self.skippoints = skipPoints
        self.clearextension = clearExtension

    def load(self, fileName):
        trackName = ""
        trackType = ""

        gpx = self.openGpx(fileName)
        listOfTracks = []
        for track in gpx.tracks:
            trackName = track.name
            trackType = track.type
            listOfSegments = []
            for segment in track.segments:
                listOfSegments.append(segment.points)

            listOfTracks.append(Track(trackName, trackType, listOfSegments))

        return listOfTracks

    def mergeWithFirst(self, fileOfFirst, otherFiles):
        gpx = self.openGpx(fileOfFirst)

        for track in otherFiles:
            newTrack = gpxpy.gpx.GPXTrack()
            newTrack.name = track.name
            newTrack.type = track.type
            for segment in track.segments:
                newSegment = gpxpy.gpx.GPXTrackSegment()
                newTrack.segments.append(newSegment)
                for point in segment:
                        newSegment.points.append(point)
            gpx.tracks.append(newTrack)

        return gpx

class MergeGpxBySegments(MergeGPX):
    def __init__(self, skipPoints:int=1, clearExtension:bool=True):
        self.skippoints = skipPoints
        self.clearextension = clearExtension

    def load(self, fileName):
        gpx = self.openGpx(fileName)

        if len(gpx.tracks) > 1:
            print("file uses for merging:", fileName, "contains more then one track !!!")
            print("Segments will be taken from all tracks and marged to track from first file")

        listOfSegments = []
        for track in gpx.tracks:
            for segment in track.segments:
                listOfSegments.append(segment.points)
        return listOfSegments

    def mergeWithFirst(self, fileOfFirst, otherFiles):
        gpx = self.openGpx(fileOfFirst)
        if len(gpx.tracks) > 1:
            print("First file contains more then one track. I do not know how to merge it")
            exit()

        for pointsOfSegment in otherFiles:
            newSegment = gpxpy.gpx.GPXTrackSegment()
            for point in pointsOfSegment:
                    newSegment.points.append(point)

            gpx.tracks[0].segments.append(newSegment)
        return gpx

class MergeGpxByPoints(MergeGPX):
    def __init__(self, skipPoints:int=1, clearExtension:bool=True):
        self.skippoints = skipPoints
        self.clearextension = clearExtension

    def load(self, fileName):
        gpx = self.openGpx(fileName)

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

    def mergeWithFirst(self, fileOfFirst, otherPoints):
        gpx = self.openGpx(fileOfFirst)
        if len(gpx.tracks) > 1:
            print("First file contains more then one track. I do not know how to merge it")
            exit()
        if len(gpx.tracks[0].segments) > 1:
            print("First file contains more then one segment. I do not know how to merge it")
            exit()
        for point in otherPoints:
                gpx.tracks[0].segments[0].points.append(point)
        return gpx

if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog = "MergeGpx", description="script to merge or editing gpx files")

    parser.add_argument("-s", "--skip", help="how much points to skip for optimization. 1 - without skipping, 2 - every second etc. Default is 1", nargs='?', dest='skippingNumber', default='1')
    parser.add_argument("-o", "--output", help="gpx output filename", required=True)
    parser.add_argument("-c","--clear", action='store_true', help="clear extension data")
    parser.add_argument('-t','--type',
                       action='store',
                       choices=['tracks', 'segments', 'points'],
                       dest='typeOfMerge',
                       help='Type of merge: tracks - tracks will be separated on the one gpx [default] \
                             segments - one track, segments will be join - good option to merge the same day of activity\
                             points - merge points to one segment - nobody will know, that you merged gpxs', default='tracks')

    parser.add_argument("path", help="directory to gpx files or path to gpx file for editing. Default value is the current directory", nargs='?', default=os.getcwd())

    args = parser.parse_args()
    path = args.path
    skippingNumber = int(args.skippingNumber)
    outputFileName=args.output
    clearExtension = args.clear
    typeOfMerge = args.typeOfMerge

    if not ".gpx" in outputFileName:
        print("output filename has to have gpx extension")
        exit()
    if os.path.isfile(outputFileName):
        print("output filename already exist")
        exit()

    mergeGpx = MergeGPX(skipPoints=skippingNumber, clearExtension=clearExtension)
    if os.path.isfile(path):
        mergeGpx.editGpx(path, outputFileName)
    elif os.path.isdir(path):
        list = os.listdir(path)
        if len(list) < 2:
            print("too less files for merge")
            exit()

        listOfGpx = []
        for x in list:
            if ".gpx" in x:
                listOfGpx.append(os.path.join(path,x))
        listOfGpx.sort()

        if typeOfMerge == "tracks":
            mergeGpx = MergeGPXByTracks()
        elif typeOfMerge == "segments":
            mergeGpx = MergeGpxBySegments()
        elif typeOfMerge == "points":
            mergeGpx = MergeGpxByPoints()

        mergeGpx.settings(skippingNumber, clearExtension)
        mergeGpx.merge(listOfGpx, outputFileName)
    else:
        print("wrong path/filename")

