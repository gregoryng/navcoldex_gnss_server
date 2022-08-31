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
import serial

import possim
import nav
import nav_nmea


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
            pass
    logging.info("nmea_serial_handler stopped.")

def main():
    parser = argparse.ArgumentParser(description="Serial-to-TCP server for GNSS receivers")

    parser.add_argument('-s', '--serial', default="/dev/ttyUSB0",
                                           help="Input serial port")

    # HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
    # PORT = 4040  # Port to listen on (non-privileged ports are > 1023)
    parser.add_argument('--host', default="localhost", help="TCP server listen hostname")
    parser.add_argument('--port', default=4040, type=int, help="TCP server listen port")
    parser.add_argument('--interval', default=1.0, type=float, help="Output position update interval (seconds)")
    # parser.add_argument('-v','--verbose', action="store_true", help="Display verbose output")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, stream=sys.stdout)


    ns = nav.NavState()
    handler = nmea_serial_handler # or simulator_handler, nmea_stdin_handler
    t_serial = threading.Thread(target=handler, args=(ns, args.serial))
    t_serial.start()
    server(ns, args.host, args.port, args.interval)


if __name__ == "__main__":
    main()
