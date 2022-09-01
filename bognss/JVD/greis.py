#!/usr/bin/env python3

# Script to break out the JVD binary data into ascii streams.
# Taken from Javad GREIS data format specification
# GNG 2-17-01-06

from collections import namedtuple
import struct
import logging
# Mostly for test
import argparse
import binascii
import sys


GREISMsg = namedtuple('GREISMsg', 'id len body')
GREISMsgParsed = namedtuple('GREISMsgParsed', 'id len body parsed')

# GREIS message definitions
messages = {
b'~~': ('<LB', namedtuple('RT','tod cs'),''),
b'RT': ('<LB', namedtuple('RT','tod cs'),''),
b'GT': ('<LHB', namedtuple('GT','tow wn cs'),''),
b'ST': ('<LBB', namedtuple('ST','time solType cs'), '{:d} {:d} {:02x}'),
b'PG': ('<dddfBB', namedtuple('PG','lat lon alt pSigma solType cs'), ''),
b'VG': ('<ffffBB', namedtuple('VG','lat lon alt vSigma solType cs'), ''),
b'SG': ('<ffffBB', namedtuple('SG','hpos vpos hvel vvel solTYpe cs'), ''),
b'PV': ('<dddfffffBB', namedtuple('PV','x y z pSigma vx vy vz vSigma solType cs'), ''),
b'TO': ('<ddB', namedtuple('TO','val sval cs'), ''),
b'DO': ('<ffB', namedtuple('DO','val sval cs'), ''),
b'RD': ('<HBBBB', namedtuple('RD','year month day base cs'), ''),
b'DP': ('<fffBB', namedtuple('DP','hdop vdop tdop solType cs'), ''),
b'AR': ('<LffffffBB', namedtuple('AR','time pitch roll heading pitchRms rollRms headingRms flags cs'), ''),
b'mR': ('<fffffffffB',namedtuple('mR','q00 q01 q02 q10 q11 q12 q20 q21 q22 cs'),''),
b'PS': ('<BBBBBBBBB', namedtuple('PS','solType gpsLocked gloLocked gpsAvail gloAvail gpsUsed gloUsed fixProg cs'), ''),
b'UO': ('<dfIHbBHbB',  namedtuple('UO','a0 a1 tot wnt dtls dn wnlsf dtlsf cs'),''),
}
# variable-length messages ({type},{bytes per element},{print_format})
# TODO: can we figure out this from the format string?
vmessages = {
b'AN': ('c',1,'{:s}'),
b'SI': ('B',1,'{:d}'),
b'NN': ('B',1,'{:d}'),
b'EL': ('b',1,'{:d}'),
b'AZ': ('b',1,'{:d}'),
b'TC': ('H',2,'{:d}'),
b'ID': ('f',4,'{:06e}'),
b'SS': ('B',1,'{:02x}'),
}
for id in b'EC E1 E2 E3 E5 EI CE 1E 2E 3E 5E IE'.split():
    vmessages[id] = ('B',1,'{:d}')
for id in b'FC F1 F2 F3 F5 FI' .split():
    vmessages[id] = ('H',2,'{:04x}')
for id in b'cc c1 c2 c3 c5 ec e1 e2 e3 e5 qc q1 q2 a3 q5 1d 2d 3d 5d ' \
          b'1r 2r 3r 5r'.split():
    vmessages[id] = ('h',2,'{:d}')
for id in b'CP 1P 2P 3P 5P'.split():
    vmessages[id] = ('f',4,'{:f}')
for id in b'R1 R2 R3 R5 PC P1 P2 P3 P5'.split():
    vmessages[id] = ('d',8,'{:f}')
for id in b'rc r1 r2 r3 r5 pc p1 p2 p3 p5 DC D1 D2 D3 D5 cp 1p 2p 3p 5p'.split():
    vmessages[id] = ('i',4,'{:d}')
for id in b'pc p1 p2 p3 p5'.split():
    vmessages[id] = ('I',4,'{:d}')
#for id in 'CC C1 C2 C3 C5 cc c1 c2 c3 c5'.split():
#    vmessages[id] = ('H',6,'{:012x}')

#    known_msgs_filtered=set(
#    ('SI AN EL AZ RC TC SS ID ' \
#     'CC C1 C2 C3 C5 cc c1 c2 c3 c5 ' \
#     'PC P1 P2 P3 P5 pc p1 p2 p3 p5 ' \
#     'CP 1P 2P 3P 5P cp 1p 2p 3p 5p ' \
#     'DC D1 D2 D3 D5 1d 2d 3d 5d ' \
#     'EC E1 E2 E3 E5 ec e1 e2 e3 e5 qc q1 q2 q3 q5 ' \
#     'CE 1E 2E 3E 5E ' \
#     'FC F1 F2 F3 F5 ' \
#    ).split(' '))



def make_xds_str(fmtstr,translator = {
        'f': '{:0.6e}','d': '{:0.15e}', 's': '{:s}',
        'B': '{:d}','b': '{:d}',        'H': '{:d}','h': '{:d}',
        'L': '{:d}','l': '{:d}',        'I': '{:d}','i': '{:d}',
        'q': '{:d}','Q': '{:d}',
    }):
    parts=[]
    for c in fmtstr:
        if c in translator:
            parts.append(translator[c])
    parts[-1] = '{:02x}'
    return ' '.join(parts)
    
for k in messages:
    if messages[k][2] == '':
        messages[k] = (messages[k][0],messages[k][1],make_xds_str(messages[k][0]) )

# End module variable definitions
##############################################################################
def GREISParser(fp, skip_crlf=False):
    """ 
    Parse out fields within known GREIS messages
    skip_crlf will have the GREIS parser not yield garbage data that consists only of \n or \r\n"""
    for data in GREISReader(fp, skip_crlf):
        # TODO: validate checksums here
        if data.id in messages:
            # known fixed-length messages
            try:
                parsed = messages[data.id][1]._make(struct.unpack( messages[data.id][0], data.body) )
                yield GREISMsgParsed._make(data + (parsed,))
            except struct.error:
                es = struct.calcsize(messages[data.id][0])
                print("# unparseable: id={:s}; input data length={:d}; expected length={:d}".format(
                    data[0].decode(), len(data.body), es ))
                yield data
        elif data.id in vmessages:
            logging.debug("data.id=%s", data.id)
            # known variable-length messages
            if data.id == 'SS':
                # TODO: make this not a special case
                slen = len(data.body)-2
                fmtstr = "<{:d}{:s}BB".format( slen // vmessages[data.id][1] , vmessages[data.id][0] )
            else:
                slen = len(data.body)-1
                fmtstr = "<{:d}{:s}B".format( slen // vmessages[data.id][1] , vmessages[data.id][0] )
                logging.debug("vvdata.id=%s slen=%d", data.id, slen)
            try:
                fields = struct.unpack(fmtstr, data.body )
            except struct.error:
                es = struct.calcsize(fmtstr)
                print("# unparseable: id={:s}; input data length={:d}; expected length={:d}; fmtstr={:s}".format(
                    data[0], len(data.body), es, fmtstr ))
                yield data
            yield GREISMsgParsed._make(data + (fields,))
        else:
            # everything else just pass it through.
            yield data
            

def GREISReader(fp, skip_crlf=False):
    '''
    Reads a GREIS standard message stream as defined in Javad GREIS Reference Guide
    
    There is no guarantee that the binary file's start will be aligned with
    the start of a data packet. This scans through the file until it
    finds a valid GREIS header
    The format of every standard message is as follows:
        struct StdMessage {var} {
            a1 id[2]; // Identifier
            a1 length[3]; // Hexadecimal body length, [000...FFF]
            u1 body[length]; // body
        };
    Each standard message begins with the unique message identifier comprising two ASCII
    characters. Any characters from the subset "0" through "~" (i.e., decimal ASCII codes in
    the range of [48...126]) are allowed in identifier.
    
    # Returns the message id, message length, message body, and any data skipped prior to this message.
    
    '''
    buffer = bytearray(b'')
    baddata = bytearray(b'')
    while True:
        if len(buffer) < 5:
            buffer += fp.read( 5 - len(buffer) )
        # if not enough data, quit
        if len(buffer) < 5:
            break

        # enforce message id restrictions
        b_msg_valid = is_headerchar(buffer[0]) and is_headerchar(buffer[1]) and \
            is_hexdigit(buffer[2]) and is_hexdigit(buffer[3]) and is_hexdigit(buffer[4])

        try:
            msglen = int(buffer[2:],16)
        except ValueError as e:
            b_msg_valid = False

        if not b_msg_valid:
            baddata.append(buffer[0])
            buffer = buffer[1:]
            continue

        msgbody = fp.read(msglen)
        # if there isn't any bad data, or it is just a line ending and we
        # are skipping bad data, then don't emit it.
        if not ((baddata == '') or (skip_crlf and (baddata == b"\n" or baddata == b"\r\n"))):
            yield GREISMsg(b'??', b'???', baddata)
        baddata = bytearray()
        yield GREISMsg(bytes(buffer[0:2]), bytes(buffer[2:]), msgbody)
        buffer = bytearray()
    # Emit the last data
    # if there isn't any bad data, or it is just a line ending and we
    # are skipping bad data, then don't emit it.
    baddata += buffer
    if not ((baddata == '') or (skip_crlf and (baddata == b"\n" or baddata == b"\r\n"))):
        yield GREISMsg(b'??',b'???', baddata)
    baddata = ''
            

def crc8(data):
    #define ROT_LEFT(val) ((val << lShift) | (val >> rShift))
    res=0
    
    for c in bytearray(data):
        res = (((res << 2) | ( res >> 6)) & 0xff) ^ c
    return ((res << 2) | ( res >> 6)) & 0xff



def is_headerchar(c):
    # b = ord(c) # python2
    # return b >= 48 and b <= 126
    return 48 <= c <= 126
def is_hexdigit(c):
    #b = ord(c)
    #return (b >= 0x30 and b <= 0x39) or (b >= 0x41 and b <= 0x46)
    return (0x30 <= c <= 0x39) or (0x41 <= c <= 0x46)


def make_xds( id, data ):
    if id in messages:
        fmtstr = messages[id][2]
        return fmtstr.format(*data)
    elif id in vmessages:
        return' '.join([ vmessages[id][2].format(x) for x in data[0:-2]]) + ' {:02x}'.format(data[-1])
    else:
        return ''
    
def test(args):
    LOGLEVEL=logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=LOGLEVEL, stream=sys.stdout)

    input_bxds = args.input
    msgcount = {}

    is_debug = logging.getLogger().isEnabledFor(logging.DEBUG)
    is_info = logging.getLogger().isEnabledFor(logging.INFO)

    with open(input_bxds, "rb") as fh:
        for data in GREISParser(fh, True):
            if is_debug:
                logging.debug("greis: {!r}".format( (data[0], data[1], binascii.b2a_hex(data[2]))))

            msgcount[data[0]] = msgcount.get(data[0], 0) + 1

            lendata = len(data)
            if lendata == 4:
                xds = make_xds( data[0], data[3] )
                print("greis: ", data[0:2], xds)
            else:
                print("greis: {!r}".format(data))

            if data[0] == b'??':
                pass
            elif data[0] == b'PM' or data[0] == b'SY': # ascii message
                cs = crc8(data[0] + data[1] + data[2][0:-2])
                csdata = int(data[2][-2:], 16)
                if cs != csdata:
                    logging.warning("Bad CRC asc (should be 0x{:02x})".format(cs))
            else:
                cs = crc8(data[0] + data[1] + data[2][0:-1])
                # if cs != ord(data[2][-1]):
                if cs != data[2][-1]:
                    logging.warning("Bad CRC bin (should be 0x{:02x})".format(cs))


    print("Message totals: ")
    for k, v in sorted(msgcount.items(), key=by_value):
        print(k, ': ', v)

def by_value(item):
    # Sort in reverse order of size and forward by name
    return (-item[1], item[0])


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('-i','--input',  help='Input directory or file',
                        required=False, default="log0104a.jps")
    parser.add_argument('-o','--output', help='Output directory or file',
                        required=False)
    parser.add_argument('-v', '--verbose', action="store_true", help='verbose output',
                        required=False)
    args = parser.parse_args()

    test(args)




if __name__ == "__main__":
    main()
