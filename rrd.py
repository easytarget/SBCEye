#import time
import rrdtool
import tempfile
import datetime
from pathlib import Path

class rrd:
    def __init__(self, path, sensor, pinMap):
        self.sensor = sensor
        self.pinMap = pinMap
        self.envDB = Path(path + "env.rrd")
        self.sysDB = Path(path + "sys.rrd")
        self.pinDB = []
        for i in range(len(self.pinMap)):
            self.pinDB.append(Path(path + self.pinMap[i][0] + ".rrd"))
        # Main RRDtool databases
        if self.sensor:
            if not self.envDB.is_file():
                print("Generating " + str(self.envDB))
                rrdtool.create(
                    str(self.envDB),
                    "--start", "now",
                    "--step", "60",
                    "RRA:AVERAGE:0.5:1:131040",   # 3 months per minute
                    "RRA:AVERAGE:0.5:60:26352",   # 3 years per hour
                    "DS:env-temp:GAUGE:60:U:U",
                    "DS:env-humi:GAUGE:60:U:U",
                    "DS:env-pres:GAUGE:60:U:U")
            else:
                print("Using existing: " + str(self.envDB))

        if not self.sysDB.is_file():
            print("Generating " + str(self.sysDB))
            rrdtool.create(
                str(self.sysDB),
                "--start", "now",
                "--step", "60",
                "RRA:AVERAGE:0.5:1:131040",   # 3 months per minute
                "RRA:AVERAGE:0.5:60:26352",   # 3 years per hour
                "DS:sys-temp:GAUGE:60:U:U",
                "DS:sys-load:GAUGE:60:U:U",
                "DS:sys-mem:GAUGE:60:U:U")
        else:
            print("Using existing: " + str(self.sysDB))
        # Add RRD database for each GPIO line
        for i in range(len(self.pinMap)):
            if not self.pinDB[i].is_file():
                print("Generating " + str(self.pinDB[i]))
                rrdtool.create(
                    str(self.pinDB[i]),
                    "--start", "now",
                    "--step", "60",
                    "RRA:AVERAGE:0.5:1:131040",   # 3 months per minute
                    "RRA:AVERAGE:0.5:60:26352",   # 3 years per hour
                    "DS:status:GAUGE:60:0:1")
            else:
                print("Using existing: " + str(self.pinDB[i]))

    def update(self, tmp, hum, pre, cpu, top, mem, states):
        if self.sensor:
            updateCmd = "N:" + format(tmp, '.3f') + ":" + format(hum, '.2f') + ":" + format(pre, '.2f')
            rrdtool.update(str(self.envDB), updateCmd)
        updateCmd = "N:" + cpu + ":" + str(top) + ":" + str(mem)
        rrdtool.update(str(self.sysDB), updateCmd)
        for i in range(len(self.pinMap)):
            updateCmd = "N:" + str(states[i])
            rrdtool.update(str(self.pinDB[i]), updateCmd)

    def drawGraph(self, period, graph, wide, high, areac, areaw, linec, linew, serverName):
        # RRD graph generation
        # Returns the generated file for sending in the http response
        tempf = tempfile.NamedTemporaryFile(mode='rb', dir='/tmp', prefix='overwatch_graph')
        start = 'end-' + period
        if (graph == "env-temp"):
            try:
                rrdtool.graph(tempf.name, "--title", "Environment Temperature: last " + period,
                              "--width", str(wide),
                              "--height", str(high),
                              "--full-size-mode",
                              "--start", start,
                              "--end", "now",
                              "--upper-limit", "50",
                              "--lower-limit", "10",
                              "--left-axis-format", "%3.1lf\u00B0C",
                              "--watermark", serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                              "DEF:envt=" + str(self.envDB) + ":env-temp:AVERAGE", areaw + 'envt' + areac, linew + 'envt' + linec)
            except Exception:
                pass
        elif (graph == "env-humi"):
            try:
                rrdtool.graph(tempf.name, "--title", "Environment Humidity: last " + period,
                              "--width", str(wide),
                              "--height", str(high),
                              "--full-size-mode",
                              "--start", start,
                              "--end", "now",
                              "--upper-limit", "100",
                              "--lower-limit", "0",
                              "--left-axis-format", "%3.0lf%%",
                              "--watermark", serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                              "DEF:envh=" + str(self.envDB) + ":env-humi:AVERAGE", areaw + 'envh' + areac, linew + 'envh' + linec)
            except Exception:
                pass
        elif (graph == "env-pres"):
            try:
                rrdtool.graph(tempf.name, "--title", "Environment Pressure: last " + period,
                              "--width", str(wide),
                              "--height", str(high),
                              "--full-size-mode",
                              "--start", start,
                              "--end", "now",
                              "--upper-limit", "1040",
                              "--lower-limit", "970",
                              "--units-exponent", "0",
                              "--left-axis-format", "%4.0lfmb",
                              "--watermark", serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                              "DEF:envp=" + str(self.envDB) + ":env-pres:AVERAGE", areaw + 'envp' + areac, linew + 'envp' + linec)
            except Exception:
                pass
        elif (graph == "sys-temp"):
            try:
                rrdtool.graph(tempf.name, "--title", "CPU Temperature: last " + period,
                              "--width", str(wide),
                              "--height", str(high),
                              "--full-size-mode",
                              "--start", start,
                              "--end", "now",
                              "--upper-limit", "80",
                              "--lower-limit", "40",
                              "--left-axis-format", "%3.1lf\u00B0C",
                              "--watermark", serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                              "DEF:syst=" + str(self.sysDB) + ":sys-temp:AVERAGE", areaw + 'syst' + areac, linew + 'syst' + linec)
            except Exception:
                pass
        elif (graph == "sys-load"):
            try:
                rrdtool.graph(tempf.name, "--title", "CPU Load Average: last " + period,
                              "--width", str(wide),
                              "--height", str(high),
                              "--full-size-mode",
                              "--start", start,
                              "--end", "now",
                              "--upper-limit", "3",
                              "--lower-limit", "0",
                              "--units-exponent", "0",
                              "--left-axis-format", "%2.3lf",
                              "--watermark", serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                              "DEF:sysl=" + str(self.sysDB) + ":sys-load:AVERAGE", areaw + 'sysl' + areac, linew + 'sysl' + linec)
            except Exception:
                pass
        elif (graph == "sys-mem"):
            try:
                rrdtool.graph(tempf.name, "--title", "System Memory Use: last " + period,
                              "--width", str(wide),
                              "--height", str(high),
                              "--full-size-mode",
                              "--start", start,
                              "--end", "now",
                              "--upper-limit", "100",
                              "--lower-limit", "0",
                              "--left-axis-format", "%3.0lf%%",
                              "--watermark", serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                              "DEF:sysm=" + str(self.sysDB) + ":sys-mem:AVERAGE", areaw + 'sysm' + areac, linew + 'sysm' + linec)
            except Exception:
                pass
        else:
            for i in range(len(self.pinMap)):
                if (graph == "pin-" + self.pinMap[i][0]):
                    try:
                        rrdtool.graph(tempf.name, "--title", self.pinMap[i][0] + " Pin State: last " + period,
                                      "--width", str(wide),
                                      "--height", str(high/2),
                                      "--full-size-mode",
                                      "--start", start,
                                      "--end", "now",
                                      "--upper-limit", "1.1",
                                      "--lower-limit", "-0.1",
                                      "--left-axis-format", "%3.1lf",
                                      "--watermark", serverName + " :: " + datetime.datetime.now().strftime("%H:%M:%S, %A, %d %B, %Y"),
                                      "DEF:pinv=" + str(self.pinDB[i]) + ":status:AVERAGE", areaw + 'pinv' + areac, linew + 'pinv' + linec)
                    except Exception:
                        pass
        response = tempf.read()
        if (len(response) == 0):
            print("Error: png file generation failed for : " + graph + " : " + period)
        tempf.close()
        return response


