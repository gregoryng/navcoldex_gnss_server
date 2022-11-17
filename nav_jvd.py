#!/usr/bin/env python3

"""
Adapter for navigation using Javad or Topcon messages
"""

import time
import sys
from collections import defaultdict
import math
import os

import bognss.JVD.greis as greis
from nav_nvt import sec_from_weeksec, gm_from_gps, utc_time
import nav



def greis_nav_gen(stream, gps_utc_offset=0, gps_weeknum_offset=1024, nmax=None):
    """ Generate NavState values from a stream of Javad GREIS messages """
    stats = defaultdict(int)
    ns = nav.NavState()

    has_gt = False

    for i, rec in enumerate(greis.GREISParser(stream, skip_crlf=True)):
        # Increment stats counter
        stats[rec[0]] += 1

        if rec.id in (b'AR', b'mR'):
            continue
        try:
            rec.parsed
        except AttributeError:
            pass

        data = {}
        if rec.id in (b'~~', b'RT') and not has_gt:
            # TODO: for now ignore the ST messages
            # TODO: doesn't do the right thing around the top of the day.
            # ignore this time if GT is present.

            tod = rec.parsed.tod - int(gps_utc_offset*1000) # Time of day in milliseconds
            data['utc_ms'] = tod % 60000
            tod = (tod - data['utc_ms']) // 60000
            data['utc_min'] = tod % 60
            tod = (tod - data['utc_min']) // 60
            data['utc_hour'] = tod
        elif rec.id in (b'GT',):
            has_gt = True
            data = utc_time(rec.parsed.wn + gps_weeknum_offset, rec.parsed.tow / 1000, gps_utc_offset)
        elif rec.id == b'PG':
            data['latitude'] = rec.parsed.lat
            data['longitude'] = rec.parsed.lon
            data['height'] = rec.parsed.alt
        elif rec.id == b'VG':
            ve, vn, vu = rec.parsed.lon, rec.parsed.lat, rec.parsed.alt
            # for bearing, north = x and east = y
            data['trk_gnd'] = math.degrees(math.atan2(ve, vn))
            data['hor_spd'] = math.sqrt(ve*ve + vn*vn)
            data['vert_spd'] = vu

        #print(repr(rec))
        ns.update(data)

        yield ns
        if nmax is not None and i >= nmax:
            break


def main():
    #infile = "/disk/kea/WAIS/targ/xped/ICP9/breakout/ELSA/F03/TOT3/JKB2s/X07a/AVNjp1/bxds"
    infile = os.path.join(os.path.dirname(__file__), 'tests/data/ICP9_F03_TOT3_JKB2s_X07a_AVNjp1_bxds')

    with open(infile, "rb") as fin:
        for mynav in greis_nav_gen(fin, nmax=1000):
            print(mynav.nav_message().strip())


if __name__ == "__main__":
    main()
