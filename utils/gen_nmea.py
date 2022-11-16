#!/usr/bin/env python3

""" 
Simple utility script for generating NMEA sentences to stdout or to serial port
"""

import math
import time
import argparse
import sys
from datetime import datetime, timedelta, timezone

from nmeasim.simulator import Simulator
from nmeasim.models import GpsReceiver


def main():
    parser = argparse.ArgumentParser(description="Generate simulated NMEA data")

    parser.add_argument('--time', type=float, default=None,
                        help="Time limit to run")
    args = parser.parse_args()

    gps = GpsReceiver(
        date_time=datetime(2022,1, 1, 12, 34, 56, tzinfo=timezone.utc),
        lat=-77.0,
        lon=165.,
        altitude=2500.,
        kph=305., # 165 kts
    )

    sim = Simulator(gps=gps)
    sim.serve(output=sys.stdout, blocking=False)

    # Run until time limit
    tf = args.time
    if args.time is not None:
        tf += time.time()

    try:
        while tf is None or time.time() < tf:
            sys.stdout.flush()
            time.sleep(0.1)
    finally:
        sim.kill()

if __name__ == "__main__":
    main()
