#!/usr/bin/env python

import argparse
import csv
import sys
import time
import logging
import config

from lib.oven import RealOven, SimulatedOven

log = logging.getLogger(__name__)
logging.basicConfig(level=config.log_level, format=config.log_format)

SIMULATE = True


def recordprofile(csvfile, targettemp):
    try:
        sys.dont_write_bytecode = True
        import config
        sys.dont_write_bytecode = False

    except ImportError:
        log.error("Could not import config file.")
        log.error("Copy config.py.EXAMPLE to config.py and adapt it for your setup.")
        exit(1)

    # open the file to log data to
    f = open(csvfile, 'w')
    csv_out = csv.writer(f)
    csv_out.writerow(['time', 'temperature'])

    # construct the oven
    if SIMULATE:
        oven = SimulatedOven()
    else:
        oven = RealOven()

    # Main loop:
    #
    # * heat the oven to the target temperature at maximum burn.
    # * when we reach it turn the heating off completely.
    # * wait for it to decay back to the target again.
    # * quit
    #
    # We record the temperature every second
    try:
        stage = 'heating'
        if not SIMULATE:
            oven.output.heat(sleep_for=0)

        while True:
            temp = oven.temperature + config.thermocouple_offset

            csv_out.writerow([time.time(), temp])
            f.flush()

            if stage == 'heating':
                if temp >= targettemp:
                    if not SIMULATE:
                        oven.output.cool(0)
                    stage = 'cooling'

            elif stage == 'cooling':
                if temp < targettemp:
                    break

            log.info("stage = %s, actual = %s, target = %s" % (stage, temp, targettemp))
            time.sleep(1)

        f.close()

    finally:
        # ensure we always shut the oven down!
        if not SIMULATE:
            oven.output.cool(0)


def line(a, b, x):
    return a * x + b


def invline(a, b, y):
    return (y - b) / a


def plot(xdata, ydata,
         tangent_min, tangent_max, tangent_slope, tangent_offset,
         lower_crossing_x, upper_crossing_x):
    from matplotlib import pyplot

    minx = min(xdata)
    maxx = max(xdata)
    miny = min(ydata)
    maxy = max(ydata)

    pyplot.scatter(xdata, ydata)

    pyplot.plot([minx, maxx], [miny, miny], '--', color='purple')
    pyplot.plot([minx, maxx], [maxy, maxy], '--', color='purple')

    pyplot.plot(tangent_min[0], tangent_min[1], 'v', color='red')
    pyplot.plot(tangent_max[0], tangent_max[1], 'v', color='red')
    pyplot.plot([minx, maxx], [line(tangent_slope, tangent_offset, minx), line(tangent_slope, tangent_offset, maxx)], '--', color='red')

    pyplot.plot([lower_crossing_x, lower_crossing_x], [miny, maxy], '--', color='black')
    pyplot.plot([upper_crossing_x, upper_crossing_x], [miny, maxy], '--', color='black')

    pyplot.show()


def calculate(filename, tangentdivisor, showplot):
    # parse the csv file
    xdata = []
    ydata = []
    filemintime = None
    with open(filename) as f:
        for row in csv.DictReader(f):
            try:
                time = float(row['time'])
                temp = float(row['temperature'])
                if filemintime is None:
                    filemintime = time

                xdata.append(time - filemintime)
                ydata.append(temp)
            except ValueError:
                continue  # just ignore bad values!

    # gather points for tangent line
    min_y = min(ydata)
    max_y = max(ydata)
    mid_y = (max_y + min_y) / 2
    y_offset = int((max_y - min_y) / tangentdivisor)
    tangent_min = tangent_max = None
    for i in range(0, len(xdata)):
        row_x = xdata[i]
        row_y = ydata[i]

        if row_y >= (mid_y - y_offset) and tangent_min is None:
            tangent_min = (row_x, row_y)
        elif row_y >= (mid_y + y_offset) and tangent_max is None:
            tangent_max = (row_x, row_y)

    # calculate tangent line to the main temperature curve
    tangent_slope = (tangent_max[1] - tangent_min[1]) / (tangent_max[0] - tangent_min[0])
    tangent_offset = tangent_min[1] - line(tangent_slope, 0, tangent_min[0])

    # determine the point at which the tangent line crosses the min/max temperaturess
    lower_crossing_x = invline(tangent_slope, tangent_offset, min_y)
    upper_crossing_x = invline(tangent_slope, tangent_offset, max_y)

    # compute parameters
    L = lower_crossing_x - min(xdata)
    T = upper_crossing_x - lower_crossing_x

    # Magic Ziegler-Nicols constants ahead!
    Kp = 1.2 * (T / L)
    Ti = 2 * L
    Td = 0.5 * L
    Ki = Kp / Ti
    Kd = Kp * Td

    # output to the user
    print("pid_kp = %s" % (Kp))
    print("pid_ki = %s" % (Ki))
    print("pid_kd = %s" % (Kd))

    if showplot:
        plot(xdata, ydata,
             tangent_min, tangent_max, tangent_slope, tangent_offset,
             lower_crossing_x, upper_crossing_x)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Kiln tuner')
    subparsers = parser.add_subparsers()
    parser.set_defaults(mode='')

    parser_profile = subparsers.add_parser('recordprofile', help='Record kiln temperature profile')
    parser_profile.add_argument('csv_file', type=str, help="The CSV file to write to.")
    parser_profile.add_argument('--targettemp', type=int, default=400, help="The target temperature to drive the kiln to (default 400).")
    parser_profile.set_defaults(mode='recordprofile')

    parser_zn = subparsers.add_parser('zn', help='Calculate Ziegler-Nicols parameters')
    parser_zn.add_argument('csv_file', type=str,
                           help="The CSV file to read from. Must contain two columns called time (time in seconds) and temperature (observed temperature)")
    parser_zn.add_argument('--showplot', action='store_true', help="If set, also plot results (requires pyplot to be pip installed)")
    parser_zn.add_argument('--tangentdivisor', type=float, default=8, help="Adjust the tangent calculation to fit better. Must be >= 2 (default 8).")
    parser_zn.set_defaults(mode='zn')

    args = parser.parse_args()

    if args.mode == 'recordprofile':
        recordprofile(args.csv_file, args.targettemp)

    elif args.mode == 'zn':
        if args.tangentdivisor < 2:
            raise ValueError("tangentdivisor must be >= 2")

        calculate(args.csvfile, args.tangentdivisor, args.showplot)

    elif args.mode == '':
        parser.print_help()
        exit(1)

    else:
        raise NotImplementedError("Unknown mode %s" % args.mode)
