# navcoldex_gnss_server

Example GNSS server for NavCOLDEX navigation GUI written by John Sonntag

`server.py` reads serial input from a GNSS receiver and creates
a TCP server that the `navcoldex` Qt GUI can receive input from.

This utility currently only supports NMEA input, but support for Novatel
binary format messages and Javad/Topcon TPS/JPS format binary messages
are also planned.

Required nmea messages are GGA and RMC.  ZDA is also recommended.
Currently, with NMEA input, vertical speed is not supported.



## Installation

Install required pip packages

```
pip3 install -r requirements.txt
```

## Usage

In its simplest form, simply run:

```
./server.py
```

You can also specify the input serial port and the TCP port and hostname to listen on,
and update interval, if needed:

```
./server.py --serial /dev/ttyUSB0 --host 192.168.1.54 --port 4040 --interval 0.5
```

Once the server is running, you can use netcat to check the output.  In another
terminal window, run:

```
netcat localhost 4040
```

You should see lines similar to the following:
```
11,00000000,144234.0,30.034083,-90.150618,1.312336,323.250000,0.020000,0.000000
11,00000000,144235.0,30.034083,-90.150618,1.312336,350.360000,0.020000,0.000000
11,00000000,144236.0,30.034083,-90.150618,1.312336,339.870000,0.020000,0.000000
```

Starting with the second comma-delimited field, these represent
UTC date, UTC time, latitude, longitude, altitude (meters), course (deg),
speed over ground, and vertical speed.




# References

See also [sonntag_nav](https://github.com/CReSIS/sonntag_nav) by CReSIS
