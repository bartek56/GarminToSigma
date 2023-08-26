import gpxpy
import gpxpy.gpx
import os
import argparse

class Track():
    def __init__(self, name:str, type:str, points:list):
        self.name = name
        self.type = type
        self.points = points

class MergeGPX():
    def __init__(self):
        pass

    def merge(self, GpxFiles:list, resultName):
        listOfGpxFiles = GpxFiles

        listTracks = []
        for gpx in listOfGpxFiles[1:]:
            track = self.loadGpx(gpx)
            if len(track.points) == 0:
                return
            listTracks.append(track)

        gpxResult = self.mergeTracksWithFirst(listOfGpxFiles[0], listTracks)

        self.save(gpxResult.to_xml(), resultName)

    def mergeTracksWithFirst(self, fileOfFirstTrack ,otherTracks:list):
        gpx_file = open(fileOfFirstTrack, 'r')
        gpx = gpxpy.parse(gpx_file)
        gpx_file.close()

        for track in otherTracks:
            newTrack = gpxpy.gpx.GPXTrack()
            newTrack.name = track.name
            newTrack.type = track.type

            newSegment = gpxpy.gpx.GPXTrackSegment()
            newTrack.segments.append(newSegment)

            newSegment.points.extend(track.points)
            gpx.tracks.append(newTrack)

        return gpx

    def save(self, fileContent, fileName):
        with open(fileName, 'w') as f:
            f.write(fileContent)

    def loadGpx(self, fileName):
        trackName = ""
        trackType = ""
        trackPoints = []

        gpx_file = open(fileName, 'r')
        gpx = gpxpy.parse(gpx_file)
        gpx_file.close()

        if len(gpx.tracks) > 1:
            print("Error:", "more tracks then one")
            return Track()

        for track in gpx.tracks:
            trackName = track.name
            trackType = track.type
            if len(track.segments) > 1:
                print("Error:", "more segments then one")
                return Track()
            for segment in track.segments:
                trackPoints = segment.points

        return Track(trackName, trackType, trackPoints)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog = "MergeGpx", description="script to merge gpx files to one long gpx")

    parser.add_argument("path", help="path to gpx files",nargs='?', default=os.getcwd())
    parser.add_argument("-o", "--output", help="gpx output filename")
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
    mergeGpx.merge(listOfGpx, outputFileName)
