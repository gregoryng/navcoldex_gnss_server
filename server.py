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
import threading

import possim

import nav

HOST = "127.0.0.1"  # Standard loopback interface address (localhost)
PORT = 4040  # Port to listen on (non-privileged ports are > 1023)

# Message output interval
interval = 1.0



def server(ns, lock):

    do_listen = True
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((HOST, PORT))
        while do_listen:
            s.listen()
            conn, addr = s.accept()
            with conn:
                print(f"Connected by {addr}")
                try:
                    while True:
                        try:
                            lock.acquire()
                            data = ns.nav_message()
                        finally:
                            lock.release()

                        conn.sendall(data.encode('UTF-8'))
                        time.sleep(1.0)
                    do_listen = False
                except BrokenPipeError:
                    print("Client disconnected. Waiting for connection")
                    do_listen = True


def serial_handler(ns, lock):
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
    t_serial.start()
    server(ns, lock)
    

    pass

if __name__ == "__main__":
    main()
