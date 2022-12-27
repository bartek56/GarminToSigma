import gpxpy
import gpxpy.gpx

class Track():
    def __init__(self, name:str, type:str, points:list):
        self.name = name
        self.type = type
        self.points = points

class MergeGPX():
    def __init__(self, GpxFiles:list, resultName):
        if len(GpxFiles) < 2:
            print("too less files for merge")
            return
        self.listOfGpxFiles = GpxFiles
        self.listOfGpxFiles.sort()

        listTracks = []
        for gpx in self.listOfGpxFiles[1:]:
            listTracks.append(self.loadGpx(gpx))

        xmlResult = self.addTracksToGpx(listOfGpx[0], listTracks)

        self.save(xmlResult, resultName)

    def createGPX(self):
        gpx = gpxpy.gpx.GPX()

        # Create first track in our GPX:
        gpx_track = gpxpy.gpx.GPXTrack()
        gpx.tracks.append(gpx_track)

        # Create first segment in our GPX track:
        gpx_segment = gpxpy.gpx.GPXTrackSegment()
        gpx_track.segments.append(gpx_segment)

        # Create points:
        gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(2.1234, 5.1234, elevation=1234))
        gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(2.1235, 5.1235, elevation=1235))
        gpx_segment.points.append(gpxpy.gpx.GPXTrackPoint(2.1236, 5.1236, elevation=1236))

        # You can add routes and waypoints, too...

        print('Created GPX:', gpx.to_xml())

    def addTracksToGpx(self, firstTrack ,otherTracks:list):

        gpx_file = open(firstTrack, 'r')
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


        #for track in gpx.tracks:
        #    trackName = track.name
        #    trackType = track.type
        #    for segment in track.segments:
        #        trackPoints = segment.points

        #print('GPX:', gpx.to_xml())
        return gpx.to_xml()

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
    listOfGpx = ["/home/bbrzozowski/Documents/priv/activity_9753410443.gpx", "/home/bbrzozowski/Documents/priv/activity_9753410445.gpx", "/home/bbrzozowski/Documents/priv/activity_9753410444.gpx"]

    MergeGPX(listOfGpx, "test.gpx")
