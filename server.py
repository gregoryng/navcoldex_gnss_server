#!/usr/bin/env python3

"""
GPS data server -- reads serial input and serves on TCP port
This script creates a data source that simulates output. 
This can be modified to read current state from another source such as GPSD or
a serial input """

import sys
import logging
import argparse
import socket
import time
import threading

# For serial
import io
import pynmea2
#import serial

import possim
import nav
import nav_nmea
import nav_nvt

def server(ns, host, port, interval=1.0):
    """ interval - Message output interval

    This routine currently only accepts one connection at a time,
    but we could easily make it accept multiple connections
    """

    do_listen = True
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        logging.info("Listening on %s:%d", host, port)
        s.bind((host, port))
        while do_listen:
            s.listen()
            conn, addr = s.accept()
            with conn:
                logging.info(f"Connected by {addr}")
                try:
                    while True:
                        data = ns.nav_message()
                        conn.sendall(data.encode('UTF-8'))
                        time.sleep(interval)
                    do_listen = False
                except BrokenPipeError:
                    logging.info("Client disconnected. Waiting for connection")
                    do_listen = True


def simulator_handler(ns, *args):
    """ Placeholder for serial handler thread """
    psim = possim.PosSimulator()
    while True:
        time.sleep(0.2)
        psim.move(0.2)
        ns1 = psim.navstate()
        ns.update(ns1)

def nmea_stdin_handler(ns, *args):
    """ To use this one with a simulator, run:
    ./utils/gen_nmea.py | ./server.py
    """
    ns2 = nav_nmea.NmeaNavState()
    for line in sys.stdin:
        ns2.update_nmea(line)
        ns.update(ns2)

def nvt_serial_handler(ns, serialport_name, *args):

    ns2 = nav_nmea.NmeaNavState()

    ser = serial.Serial(serialport_name, 38400, timeout=1.)
    #sio = io.TextIOWrapper(io.BufferedRWPair(ser, ser))

    for ns2 in nav_nvt.nvt_nav_gen(ser):
        try:
            ns.update(ns2)
        except KeyboardInterrupt:
            break

def nvt_sim_handler(ns, serialport_name, *args):
    infile = "/disk/kea/WAIS/targ/xped/ICP9/breakout/ELSA/F03/TOT3/JKB2s/X07a/AVNnp1/bxds"
    ns2 = nav_nmea.NmeaNavState()
    t0 = None
    with open(infile, "rb") as fin:
        try:
            for ns2 in nav_nvt.nvt_nav_gen(fin):
                # Delay until appropriate time to issue message
                t1 = time.time()
                if t0 is None:
                    t0 = (t1, ns2.datetime()) # Initial message
                else:
                    rtime = t1 - t0[0]
                    rtime_msg = (ns2.datetime() - t0[1]).total_seconds()
                    dt = rtime_msg - rtime
                    if dt > 0:
                        time.sleep(dt)
                print(ns2.nav_message().strip())
                ns.update(ns2)

        except KeyboardInterrupt:
            pass


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
    logging.info("nmea_serial_handler stopped.")


def main():
    parser = argparse.ArgumentParser(description="Serial-to-TCP server for GNSS receivers")

    parser.add_argument('-s', '--serial', default="/dev/ttyUSB0",
                        help="Input serial port")
    parser.add_argument('--format', default='nmea', choices=('nmea', 'nvt', 'jvd'),
                        help="Serial input data format (default: nmea)")
    # HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
    # PORT = 4040  # Port to listen on (non-privileged ports are > 1023)
    parser.add_argument('--host', default="localhost", help="TCP server listen hostname")
    parser.add_argument('--port', default=4040, type=int, help="TCP server listen port")
    parser.add_argument('--interval', default=1.0, type=float, help="Output position update interval (seconds)")
    # parser.add_argument('-v','--verbose', action="store_true", help="Display verbose output")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)

    handlers = {
        'nmea': nmea_serial_handler,
        'nvt': nvt_sim_handler, #nvt_serial_handler,
        'jvd': None,
         # or simulator_handler, nmea_stdin_handler
    }

    ns = nav.NavState()
    t_serial = threading.Thread(target=handlers[args.format], args=(ns, args.serial))
    t_serial.start()
    server(ns, args.host, args.port, args.interval)


if __name__ == "__main__":
    main()
