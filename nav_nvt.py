#!/usr/bin/env python3

"""
Navigation adapter for Novatel binary message stream
"""

import time
import sys
from collections import defaultdict
import math

import bognss.NVT.nvt as nvt
import nav



def sec_from_weeksec(weeks, secs):
    return weeks*7*24*60*60 + secs

def gm_from_gps(gps_secs):
    '''
    GPS epoch is Jan 6, 1980, which corresponds to time.gmtime(329097600)
    '''
    gm_time = time.gmtime(gps_secs + 329097600)
    return gm_time

def nvt_nav_gen(stream, nmax=None):
    """ Generate NavState values from a stream of novatel messages """
    stats = defaultdict(int)
    ns = nav.NavState()

    for i, rec in enumerate(nvt.NovatelParser(stream, msgids=None, b_calc_crc=False, b_correct_crc=False)):
        # Increment stats counter
        stats[rec.header.msgid] += 1

        if rec.header.msgid in (140, 320, 325): #  skip these outright.
            continue

        data = {}
        if rec.header.msgid == 263: # INSATT
            data = parse_time(rec.parsed)
        elif rec.header.msgid in (42, 423): # BESTPOS, BESTGPSPOS
            data = parse_time(rec.parsed)
            for k1, k2 in (('lat', 'latitude'), ('lon', 'longitude'), ('hgt', 'height')):
                data[k2] = getattr(rec.parsed, k1)
        elif rec.header.msgid in (99, 506): # BESTVEL, BESTGPSVEL
            data = parse_time(rec.parsed)
            # vel_type latency age hor_spd trk_gnd vert_spd resvd1 crc
            for k1 in 'hor_spd trk_gnd vert_spd'.split():
                data[k1] = getattr(rec.parsed, k1)
        elif rec.header.msgid in (507, 508): # INSPVA, INSPVAS
            data = parse_time(rec.parsed)
            for k1, k2 in (('lat', 'latitude'), ('lon', 'longitude'), ('hgt', 'height'),
                ('vu', 'vert_spd') ):
                data[k2] = getattr(rec.parsed, k1)
            ve, vn = rec.parsed.ve, rec.parsed.vn

            # for bearing, north = x and east = y
            data['trk_gnd'] = math.degrees(math.atan2(ve, vn))
            data['hor_spd'] = math.sqrt(ve*ve + vn*vn)

        ns.update(data)

        yield ns
        if nmax is not None and i >= nmax:
            break

def parse_time(parsed):
    data = {}
    gpstime = gm_from_gps(sec_from_weeksec(parsed.gnssweek, parsed.gnsssec))
    for k1, k2 in (
        ('tm_year', 'utc_year'),
        ('tm_mon', 'utc_month'),
        ('tm_mday', 'utc_day'),
        ('tm_hour', 'utc_hour'),
        ('tm_min', 'utc_min')):

        data[k2] = getattr(gpstime, k1)

        data['utc_ms'] = int((parsed.gnsssec % 60.) * 1000)
    return data


def main():
    infile = "/disk/kea/WAIS/orig/xped/ICP9/acqn/NVT/F01/SPAN_1.LOG"
    infile = "/disk/kea/WAIS/targ/xped/ICP9/breakout/ELSA/F03/TOT3/JKB2s/X07a/AVNnp1/bxds"

    with open(infile, "rb") as fin:
        for mynav in nvt_nav_gen(fin, nmax=1000):
            print(mynav.nav_message().strip())


if __name__ == "__main__":
    main()
