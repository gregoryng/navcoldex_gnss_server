from dataclasses import dataclass
import threading
import datetime

@dataclass
class NavState:
    """ Navigation state in SI units """
    utc_year: int=1980
    utc_month: int=1
    utc_day: int=1
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

    def __post_init__(self):
        self.lock_ = threading.Lock()
        self.formatstr_ = "11,%04d%02d%02d,%02d%02d%02d.%01d,%f,%f,%f,%f,%f,%f\n"


    def nav_message(self):
        """ Construct a navigation message based on the current state """
        self.lock_.acquire()
        try:
            fields = (
            self.utc_year, self.utc_month, self.utc_day,
            self.utc_hour, self.utc_min, self.utc_ms/1000, self.utc_ms/100%10,
            self.latitude, self.longitude, self.height*3.28083989501, #// 3.28... to convert metres->feet
            self.trk_gnd, self.hor_spd*1.94384449, self.vert_spd*196.850393701 #//1.94... to convert m/s->knots, 196.85... to convert m/s->fpm
            )
        finally:
            self.lock_.release()

        return self.formatstr_ % fields

    def update(self, other):
        """ Update the public member variables of this variable from other """
        self.lock_.acquire()
        try:
            obj = other if isinstance(other, dict) else other.__dict__

            for k, v in obj.items():
                if not k.endswith('_'): # skip private members
                    setattr(self, k, v)
        finally:
            self.lock_.release()

    def datetime(self):
        """ Return current UTC time as a time object """
        sec = self.utc_ms // 1000
        ms = self.utc_ms  % 1000
        dtobj = datetime.datetime(self.utc_year, self.utc_month, self.utc_day,
                                  self.utc_hour, self.utc_min, sec, ms * 1000)
        return dtobj
