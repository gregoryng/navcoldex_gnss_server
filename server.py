#!/usr/bin/env python3

"""
GPS data server -- reads serial input and serves on TCP port
This script creates a data source that simulates output. 
This can be modified to read current state from another source such as GPSD or
a serial input """

import sys
import os
import logging
import argparse
import socket
import time
import threading

# For serial
import io
import pynmea2
import serial

import possim
import nav
import nav_nmea
import nav_nvt
import nav_jvd

def server(ns, host, port, interval=1.0, timeout=None):
    """ interval - Message output interval

    This routine currently only accepts one connection at a time,
    but we could easily make it accept multiple connections

    timeout specifies the number of seconds to run the server before
    quitting.
    """

    t0 = time.time()
    do_listen = True
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        logging.info("Listening on %s:%d", host, port)
        s.bind((host, port))
        while do_listen:
            try:
                if timeout is not None and time.time() - t0 > timeout:
                    break #do_listen = False
                s.settimeout(2) # listen briefly
                s.listen()
                conn, addr = s.accept()
            except socket.timeout:
                continue
            with conn:
                logging.info(f"Connected by {addr}")
                try:
                    while True:
                        data = ns.nav_message()
                        conn.sendall(data.encode('UTF-8'))
                        time.sleep(interval)
                        if timeout is not None and time.time() - t0 > timeout:
                            do_listen = False
                            break
                    do_listen = False
                except BrokenPipeError:
                    logging.info("Client disconnected. Waiting for connection")
                    do_listen = True

class StreamDelayer:
    """ When reading messages from a stream, delay them until appropriate time
    for their internal timestamps """
    def __init__(self):
        self.t0 = None

    def update(self, msgtime, delay=True, now=None):
        if now is None:
            now = time.time()

        if self.t0 is None:
            self.t0 = (now, msgtime) # Initial message
            return 0.

        rtime = now - self.t0[0]
        rtime_msg = (msgtime - self.t0[1]).total_seconds()
        dt = max(0., rtime_msg - rtime)
        if delay:
            time.sleep(dt)
        return dt

def simulator_handler(ns, *args):
    """ Placeholder for serial handler thread, just simulates movement """

    _, _, _, timeout = args
    t0 = time.time()

    psim = possim.PosSimulator()
    while True:
        time.sleep(0.2)
        psim.move(0.2)
        ns1 = psim.navstate()
        ns.update(ns1)
        if timeout is not None and time.time() - t0 > timeout:
            break

def nmea_stdin_handler(ns, *args):
    """ To use this one with a simulator, run:
    ./utils/gen_nmea.py | ./server.py
    """
    ns2 = nav_nmea.NmeaNavState()
    for line in sys.stdin:
        ns2.update_nmea(line)
        ns.update(ns2)


def nvt_serial_handler(ns, serialport_name, utcoffset, *args):
    ser = serial.Serial(serialport_name, 38400, timeout=1.)
    navgen = nav_nvt.nvt_nav_gen(ser, utcoffset)
    nvt_handler(ns, navgen, timeout)

def nvt_handler(ns, navgen, timeout):
    # Even though we don't need the 1980 check,
    # the javad handler is close enough.
    jvd_handler(ns, navgen, timeout)

def jvd_handler(ns, navgen, timeout):
    t0 = time.time()
    try:
        for ns2 in navgen:
            if ns2.datetime().year == 1980:
                continue
            ns.update(ns2)
            if timeout is not None and time.time() - t0 > timeout:
                break
    except KeyboardInterrupt:
        pass


def jvd_serial_handler(ns, serialport_name, utcoffset, gpsweekoffset, *args):
    ser = serial.Serial(serialport_name, 38400, timeout=1.)
    navgen = nav_jvd.greis_nav_gen(ser, utcoffset, gpsweekoffset)
    jvd_handler(ns, navgen)


def nvt_sim_generator(infile, utcoffset, timeout):
    """ Reads novatel messages, converts them to nav messages, and
    delays them to an appropriate time """
    sdelay = StreamDelayer()
    with open(infile, "rb") as fin:
        for ns2 in nav_nvt.nvt_nav_gen(fin, utcoffset):
            # Delay until appropriate time to issue message
            dtobj = ns2.datetime()
            sdelay.update(msgtime=dtobj, delay=True)
            logging.info(ns2.nav_message().strip())
            yield ns2


def nvt_sim_handler(ns, _, utcoffset, *args):
    _, timeout = args
    t0 = time.time()
    #infile = "/disk/kea/WAIS/targ/xped/ICP9/breakout/ELSA/F03/TOT3/JKB2s/X07a/AVNnp1/bxds"
    #if not os.path.exists(infile):
    logging.info("nvt sim handler")
    infile = os.path.join(os.path.dirname(__file__), 'tests/data/ICP9_F03_TOT3_JKB2s_X07a_AVNnp1_bxds')
    navgen = nvt_sim_generator(infile, utcoffset, timeout)
    nvt_handler(ns, navgen, timeout)

def jvd_sim_generator(infile, utcoffset, weekoffset):
    """ Generates jvd messages delayed to the appropriate time """
    sdelay = StreamDelayer()
    with open(infile, "rb") as fin:
        for ns2 in nav_jvd.greis_nav_gen(fin, utcoffset, weekoffset):
            # Delay until appropriate time to issue message
            dtobj = ns2.datetime()
            if dtobj.year == 1980:
                continue
            sdelay.update(msgtime=dtobj, delay=True)
            logging.info(ns2.nav_message().strip())
            yield ns2


def jvd_sim_handler(ns, _, utcoffset, weekoffset, *args):
    (timeout,) = args
    t0 = time.time()
    #infile = "/disk/kea/WAIS/targ/xped/ICP9/breakout/ELSA/F03/TOT3/JKB2s/X07a/AVNjp1/bxds"
    #if not os.path.exists(infile):
    infile = os.path.join(os.path.dirname(__file__), 'tests/data/ICP9_F03_TOT3_JKB2s_X07a_AVNjp1_bxds')
    navgen = jvd_sim_generator(infile, utcoffset, weekoffset)
    jvd_handler(ns, navgen, timeout)


def nmea_serial_handler(ns, serialport_name, *args):
    """ To use this one with a simulator, run:
    ./utils/gen_nmea.py | ./server.py
    """

    ns2 = nav_nmea.NmeaNavState()

    ser = serial.Serial(serialport_name, 9600, timeout=1.)
    sio = io.TextIOWrapper(io.BufferedRWPair(ser, ser))

    while True:
        try:
            line = sio.readline()
            ns2.update_nmea(line)
            ns.update(ns2)
        except serial.SerialException as e:
            logging.error('Device error: %r', e)
            break
        except (pynmea2.ParseError, UnicodeDecodeError) as e:
            logging.warning('Parse error: %s', e)
            continue
        except KeyboardInterrupt:
            break
        except Exception as e:
            logging.warning('Unhandled exception: %r', e)
            time.sleep(0.1) # prevent lockup and continue

    logging.info("nmea_serial_handler stopped.")


def main():
    handlers = {
        'nmea': nmea_serial_handler,
        'nvt': nvt_serial_handler,
        'jvd': jvd_serial_handler,
        'sim': simulator_handler,
        'nmeasim': nmea_stdin_handler,
        'nvtsim': nvt_sim_handler,
        'jvdsim': jvd_sim_handler,
    }


    parser = argparse.ArgumentParser(description="Serial-to-TCP server for GNSS receivers")

    parser.add_argument('-s', '--serial', default="/dev/ttyUSB0",
                        help="Input serial port")
    parser.add_argument('--format', default='nmea', choices=list(handlers.keys()),
                        help="Serial input data format (default: nmea)")
    # HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
    # PORT = 4063  # Port to listen on (non-privileged ports are > 1023)
    parser.add_argument('--host', default="localhost", help="TCP server listen hostname")
    parser.add_argument('--port', default=4063, type=int, help="TCP server listen port")
    parser.add_argument('--interval', default=1.0, type=float, help="Output position update interval (seconds)")

    parser.add_argument('--gpsutcoffset', default=18., type=float, help="Default GPS-UTC offset in seconds")
    parser.add_argument('--gpsweekoffset', default=1024, type=int, help="GPS week offset (GPS WNRO, for Javad input only)")
    parser.add_argument('--timeout', default=None, type=float, help="Time to run server before quitting")
    # parser.add_argument('-v','--verbose', action="store_true", help="Display verbose output")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    ns = nav.NavState()
    t_serial = threading.Thread(target=handlers[args.format], args=(ns, args.serial, args.gpsutcoffset, args.gpsweekoffset, args.timeout))
    t_serial.start()
    server(ns, args.host, args.port, args.interval, timeout=args.timeout)

if __name__ == "__main__":
    main()
