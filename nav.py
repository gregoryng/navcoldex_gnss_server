#!/usr/bin/env python3

#import geo

from dataclasses import dataclass


@dataclass
class NavState:
    """ Navigation state in SI units """
    utc_year: int=0
    utc_month: int=0
    utc_day: int=0
    utc_hour: int=0
    utc_min: int=0
    utc_ms: int=0
    # lat/lon in degrees
    latitude: float=0.
    longitude: float=0.
    # height in meters
    height: float=0.
    # ground track in degrees
    trk_gnd: float=0.
    # speeds in meters/sec
    hor_spd: float=0.
    vert_spd: float=0.

    def nav_message(self):
        """ Construct a navigation message based on the current state """
        formatstr = "11,%04d%02d%02d,%02d%02d%02d.%01d,%f,%f,%f,%f,%f,%f\n"
        s = formatstr % (
            self.utc_year, self.utc_month, self.utc_day,
            self.utc_hour, self.utc_min, self.utc_ms/1000, self.utc_ms/100%10,
            self.latitude, self.longitude, self.height*3.28083989501, #// 3.28... to convert metres->feet
            self.trk_gnd, self.hor_spd*1.94384449, self.vert_spd*196.850393701 #//1.94... to convert m/s->knots, 196.85... to convert m/s->fpm
        )
        return s

    def update(self, other):
        """ Update the member variables of this variable from other """
        for k, v in other.__dict__.items():
            setattr(self, k, v)

    #def set_time(self, 

  #if (socket->state() == QAbstractSocket::ConnectedState) {

if __name__ == "__main__":
    main()
