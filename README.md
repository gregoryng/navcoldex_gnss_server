# navcoldex_gnss_server

Example GNSS server for NavCOLDEX navigation GUI written by John Sonntag

`server.py` reads serial input from a GNSS receiver and creates
a TCP server that the `navcoldex` Qt GUI can receive input from.

This utility  supports NMEA input, Novatel binary format messages
and Javad/Topcon TPS/JPS format binary messages.

See below for recommended messages for each input format.



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
and interval (in seconds) of messages sent from server to client, if needed:

```
./server.py --serial /dev/ttyUSB0 --host 192.168.1.54 --port 4040 --interval 0.5
```

Select the input data format using the `--format` flag:

```
./server.py --format nvt
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



## Recommended Messages

For NMEA input, GGA, RMC, and ZDA message are recommended.  In NMEA input mode,
vertical speed is not currently supported.


For NOVATEL input, messages that provide position and velocity are recommended.
Either of the following two combinations would work:

- (BESTPOS or BESTGPSPOS) and (BESTVEL or BESTGPSVEL)
- INSPVA or INSPVAS


For JAVAD input, `GT`, `PG`, and `VG` messages are recommended.

# References

See also [sonntag_nav](https://github.com/CReSIS/sonntag_nav) by CReSIS
