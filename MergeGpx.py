import gpxpy
import gpxpy.gpx
import os
import argparse

class Track():
    def __init__(self, name:str, type:str, segments:list):
        self.name = name
        self.type = type
        self.segments = segments

class MergeGPX():
    def __init__(self):
        pass

    def mergeByTracks(self, GpxFiles:list, resultName):
        listOfGpxFiles = GpxFiles

        listTracks = []
        for gpx in listOfGpxFiles[1:]:
            tracks = self.loadTracksFromGpx(gpx)
            if len(tracks) == 0:
                print("file", gpx, "doesn't contain tracks. This file was skipped")
                continue
            for track in tracks:
                listTracks.append(track)

        gpxResult = self.mergeTracksWithFirst(listOfGpxFiles[0], listTracks)

        self.save(gpxResult.to_xml(), resultName)

    def loadTracksFromGpx(self, fileName):
        trackName = ""
        trackType = ""
        trackPoints = []

        gpx_file = open(fileName, 'r')
        gpx = gpxpy.parse(gpx_file)
        gpx_file.close()

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

        for track in otherTracks:
            newTrack = gpxpy.gpx.GPXTrack()
            newTrack.name = track.name
            newTrack.type = track.type
            for segment in track.segments:
                newSegment = gpxpy.gpx.GPXTrackSegment()
                newTrack.segments.append(newSegment)
                newSegment.points.extend(segment)
            gpx.tracks.append(newTrack)

        return gpx

    def loadSegmentsFromGpx(self, fileName):
        gpx_file = open(fileName, 'r')
        gpx = gpxpy.parse(gpx_file)
        gpx_file.close()

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
        if len(gpx.tracks) > 1:
            print("First file contains more then one track. I do not know how to merge it")
            exit()

        for pointsOfSegment in otherSegments:
            newSegment = gpxpy.gpx.GPXTrackSegment()
            newSegment.points.extend(pointsOfSegment)

            gpx.tracks[0].segments.append(newSegment)
        return gpx

    def mergeByPoints(self, GpxFiles:list, resultName):
        print("Merge by points is not supported")

    def save(self, fileContent, fileName):
        with open(fileName, 'w') as f:
            f.write(fileContent)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog = "MergeGpx", description="script to merge gpx files to one long gpx")

    parser.add_argument("path", help="path to gpx files",nargs='?', default=os.getcwd())
    parser.add_argument("-o", "--output", help="gpx output filename")
    parser.add_argument('-t','--type',
                       action='store',
                       choices=['tracks', 'segments', 'points'],
                       dest='typeOfMerge',
                       help='Type of merge: tracks - tracks will be separated on the one gpx [default] \
                             segments - one track, segments will be join - good option to merge the same day of activity\
                             points - merge points to one segment - nobody will know, that you merged gpxs', default='tracks')

    args = parser.parse_args()

    path = args.path
    outputFileName=args.output

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

    mergeGpx = MergeGPX()
    if args.typeOfMerge == "tracks":
        mergeGpx.mergeByTracks(listOfGpx, outputFileName)
    elif args.typeOfMerge == "segments":
        mergeGpx.mergeBySegments(listOfGpx, outputFileName)
    elif args.typeOfMerge == "points":
        mergeGpx.mergeByPoints(listOfGpx, outputFileName)
