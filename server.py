#!/usr/bin/env python3

# GPS server
""" This script creates a data source that simulates output. 
This can be modified to read current state from another source such as GPSD or
a serial input """

import sys
import logging
import argparse
import socket
import time

import possim

import nav

HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
PORT = 4040  # Port to listen on (non-privileged ports are > 1023)

# Message output interval
interval = 1.0



def old():
    psim = possim.PosSimulator()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        s.listen()
        conn, addr = s.accept()
        with conn:
            print(f"Connected by {addr}")

            while True:
                psim.move(1.0)
                data = psim.navstate().nav_message().encode('UTF-8')
                #print(data)
                conn.sendall(data)

                time.sleep(1.0)


def serial_handler(ns, lock, quit):
    """ Placeholder for serial handler thread """
    psim = possim.PosSimulator()
    while True:
        time.sleep(0.2)
        psim.move(0.2)
        ns1 = psim.navstate()
        try:
            lock.acquire()
            ns.update(ns1)
        finally:
            lock.release()


def main():
    #https://docs.python.org/3/library/threading.html#timer-objects
    ns = nav.NavState()
    lock = threading.Lock()
    t_serial = threading.Thread(target=serial_handler, args=(ns, lock))


    

    pass

if __name__ == "__main__":
    main()
