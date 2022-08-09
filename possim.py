#!/usr/bin/env python3

# Geographic calculation library
#import pymap3d as pm

import pymap3d.vincenty as pmv

import nav

class PosSimulator:
    def __init__(self, time0=0., lat0=0., lon0=0., alt0=0., heading=0., hspeed=1.0, vspeed=0.0):
        self.time = time0
        self.set_pos(lat0, lon0, alt0)
        self.set_vel(heading, hspeed, vspeed)

    def set_pos(self, lat0, lon0, alt0):
        self.lat = lat0
        self.lon = lon0
        self.alt = alt0

    def set_vel(self, heading=0., hspeed=1.0, vspeed=0.0):
        self.heading = heading
        self.hspeed = hspeed
        self.vspeed = vspeed


    def move(self, dt):
        """ Move based on elapsed time """

        d_horiz = dt * self.hspeed
        d_vert = dt * self.vspeed

        lat, lon = pmv.vreckon(self.lat, self.lon, Rng=d_horiz, Azim=self.heading)


        self.lat = lat
        self.lon = lon
        self.alt += d_vert
        self.time += dt


    def navstate(self):
        """ Return a nav.NavState object representing current state """
        ns = nav.NavState(
            latitude=self.lat, longitude=self.lon, height=self.alt,
            trk_gnd=self.heading, hor_spd=self.hspeed, vert_spd=self.vspeed)
        return ns

def main():
    psim = PosSimulator(heading=45.)


    for ii in range(100):
        psim.move(1)

        print(psim.time, psim.lat, psim.lon, psim.alt)


if __name__ == "__main__":
    main()
