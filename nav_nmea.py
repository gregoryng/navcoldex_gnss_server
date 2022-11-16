#!/usr/bin/env python3

"""
Usage:

./utils/gen_nmea.py | ./parsenmea.py

"""

import sys

import pynmea2

import nav

def convert_speed(speed, units_in='N', units_out='M'):
    # convert knots to m/s
    assert units_in == 'N' and units_out == 'M'
    speed_m = speed / 1.94384
    return speed_m

def convert_len(mylen, units_in='M', units_out='M'):
    assert units_in == units_out
    return mylen


class NmeaNavState(nav.NavState):
    def update_nmea(self, line, check=False):
        """ Update the navigation state from a nmea message """
        msg = pynmea2.parse(line, check=check)
        # we need time, lat, lon, alt, ground track, h speed and v speed
        # use duck typing to figure out nav state
        # Interested in GGA GLL RMC VTG (probably not GSA GSV ZDA
        # GLL has timestamp, lat lon (but no alt)
        # VTG has true track, speed over ground
        # So there is no message that has vertical speed
        msgtype = type(msg).__name__
        if msgtype in ('GGA', 'RMC', 'ZDA'):
            method = getattr(self, 'update_' + msgtype)
            method(msg)


    @staticmethod
    def get_utc_time(timestamp):
        """ Set the UTC time fields (but not date fields) from the timestamp """
        return {
            'utc_hour': timestamp.hour,
            'utc_min': timestamp.minute,
            'utc_ms': timestamp.second*1000
        }

    def update_GGA(self, msg):
        # GGA has time, lat, lon, alt
        fields = NmeaNavState.get_utc_time(msg.timestamp)
        fields['latitude'] = msg.latitude
        fields['longitude'] = msg.longitude
        fields['height'] = convert_len(msg.altitude, units_in=msg.altitude_units, units_out='M')
        self.update(fields)


    def update_RMC(self, msg):
        # RMC has time, lat, lon, speed over ground, course
        fields = NmeaNavState.get_utc_time(msg.timestamp)
        fields['latitude'] = msg.latitude
        fields['longitude'] = msg.longitude
        fields['hor_spd'] = convert_speed(msg.spd_over_grnd, units_in='N', units_out='M')
        fields['trk_gnd'] = msg.true_course
        self.update(fields)

    def update_VTG(self, msg):
        # VTG has true track, speed over ground
        raise NotImplementedError('Use RMC instead of VTG')

    def update_ZDA(self, msg):
        self.update({
            'utc_year': msg.year,
            'utc_month': msg.month,
            'utc_day': msg.day,
        })



def main():
    print("Starting parsenmea")
    mynav = NmeaNavState()

    for line in sys.stdin:
        try:
            msg = pynmea2.parse(line)
        except pynmea2.nmea.ParseError:
            # Perhaps log a warning?
            continue
        print(type(msg), "---", type(msg).__name__)
        mynav.update_nmea(line)
        print("       ", mynav.nav_message())


if __name__ == "__main__":
    main()
