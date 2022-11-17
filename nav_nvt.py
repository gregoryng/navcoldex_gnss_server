#!/usr/bin/env python3

"""
Navigation adapter for Novatel binary message stream
TODO: convert GPS time to UTC time
"""

import time
import sys
import os
from collections import defaultdict
import math
import logging

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

def nvt_nav_gen(stream, gps_utc_offset, nmax=None):
    """ Generate NavState values from a stream of novatel messages """
    stats = defaultdict(int)
    ns = nav.NavState()

    for i, rec in enumerate(nvt.NovatelParser(stream, msgids=None, b_calc_crc=False, b_correct_crc=False)):
        # Increment stats counter
        stats[rec.header.msgid] += 1

        if rec.header.msgid in (140, 320, 325): #  skip these outright.
            continue

        data = {}

        if rec.parsed is None:
            logging.debug("Unparseable novatel message")
            continue # if it didn't parse right, skip it
        if rec.header.msgid == 263: # INSATT
            data = utc_time(rec.parsed.gnssweek, rec.parsed.gnsssec, gps_utc_offset)
        elif rec.header.msgid in (42, 423): # BESTPOS, BESTGPSPOS
            data = utc_time(rec.parsed.gnssweek, rec.parsed.gnsssec, gps_utc_offset)
            for k1, k2 in (('lat', 'latitude'), ('lon', 'longitude'), ('hgt', 'height')):
                data[k2] = getattr(rec.parsed, k1)
        elif rec.header.msgid in (99, 506): # BESTVEL, BESTGPSVEL
            data = utc_time(rec.parsed.gnssweek, rec.parsed.gnsssec, gps_utc_offset)
            # vel_type latency age hor_spd trk_gnd vert_spd resvd1 crc
            for k1 in 'hor_spd trk_gnd vert_spd'.split():
                data[k1] = getattr(rec.parsed, k1)
        elif rec.header.msgid in (507, 508): # INSPVA, INSPVAS
            data = utc_time(rec.parsed.gnssweek, rec.parsed.gnsssec, gps_utc_offset)
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

def utc_time(gnssweek, gnsssec, gps_utc_offset_sec=0.):
    data = {}
    gpstime = gm_from_gps(sec_from_weeksec(gnssweek, gnsssec) - gps_utc_offset_sec)
    for k1, k2 in (
        ('tm_year', 'utc_year'),
        ('tm_mon', 'utc_month'),
        ('tm_mday', 'utc_day'),
        ('tm_hour', 'utc_hour'),
        ('tm_min', 'utc_min')):

        data[k2] = getattr(gpstime, k1)

        data['utc_ms'] = int((gnsssec % 60.) * 1000)
    return data


def main():
    infile = "/disk/kea/WAIS/orig/xped/ICP9/acqn/NVT/F01/SPAN_1.LOG"
    #infile = "/disk/kea/WAIS/targ/xped/ICP9/breakout/ELSA/F03/TOT3/JKB2s/X07a/AVNnp1/bxds"
    # A sample from the above file
    infile = os.path.join(os.path.dirname(__file__), 'tests/data/ICP9_03_TOT3_JKB2s_X07a_AVNnp1_bxds')


    with open(infile, "rb") as fin:
        for mynav in nvt_nav_gen(fin, gps_utc_offset=18, nmax=1000):
            print(mynav.nav_message().strip())


if __name__ == "__main__":
    main()
