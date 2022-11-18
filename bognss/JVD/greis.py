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
GMsgDef = namedtuple('GMsgDef', 'struct dtype fmt')
messages = {
b'~~': GMsgDef(struct.Struct('<LB'), namedtuple('RT','tod cs'),''),
b'RT': GMsgDef(struct.Struct('<LB'), namedtuple('RT','tod cs'),''),
b'GT': GMsgDef(struct.Struct('<LHB'), namedtuple('GT','tow wn cs'),''),
b'ST': GMsgDef(struct.Struct('<LBB'), namedtuple('ST','time solType cs'), '{:d} {:d} {:02x}'),
b'PG': GMsgDef(struct.Struct('<dddfBB'), namedtuple('PG','lat lon alt pSigma solType cs'), ''),
b'VG': GMsgDef(struct.Struct('<ffffBB'), namedtuple('VG','lat lon alt vSigma solType cs'), ''),
b'SG': GMsgDef(struct.Struct('<ffffBB'), namedtuple('SG','hpos vpos hvel vvel solTYpe cs'), ''),
b'PV': GMsgDef(struct.Struct('<dddfffffBB'), namedtuple('PV','x y z pSigma vx vy vz vSigma solType cs'), ''),
b'TO': GMsgDef(struct.Struct('<ddB'), namedtuple('TO','val sval cs'), ''),
b'DO': GMsgDef(struct.Struct('<ffB'), namedtuple('DO','val sval cs'), ''),
b'RD': GMsgDef(struct.Struct('<HBBBB'), namedtuple('RD','year month day base cs'), ''),
b'DP': GMsgDef(struct.Struct('<fffBB'), namedtuple('DP','hdop vdop tdop solType cs'), ''),
b'AR': GMsgDef(struct.Struct('<LffffffBB'), namedtuple('AR','time pitch roll heading pitchRms rollRms headingRms flags cs'), ''),
b'mR': GMsgDef(struct.Struct('<fffffffffB'),namedtuple('mR','q00 q01 q02 q10 q11 q12 q20 q21 q22 cs'),''),
b'PS': GMsgDef(struct.Struct('<BBBBBBBBB'), namedtuple('PS','solType gpsLocked gloLocked gpsAvail gloAvail gpsUsed gloUsed fixProg cs'), ''),
b'UO': GMsgDef(struct.Struct('<dfIHbBHbB'),  namedtuple('UO','a0 a1 tot wnt dtls dn wnlsf dtlsf cs'),''),
}
# variable-length messages ({type},{bytes per element},{print_format})
# TODO: can we figure out this from the format string?
# nbytes is unused
# TODO: simplify the code by making the struct construction somewhere else
VMsg = namedtuple('VMsg', 'type nbytes fmt')
vmessages = {
b'AN': VMsg(struct.Struct('<c'), 1, lambda c: c.decode()),
b'SI': VMsg(struct.Struct('<B'), 1, '{:d}'.format),
b'NN': VMsg(struct.Struct('<B'), 1, '{:d}'.format),
b'EL': VMsg(struct.Struct('<b'), 1, '{:d}'.format),
b'AZ': VMsg(struct.Struct('<b'), 1, '{:d}'.format),
b'TC': VMsg(struct.Struct('<H'), 2, '{:d}'.format),
b'ID': VMsg(struct.Struct('<f'), 4, '{:06e}'.format),
b'SS': VMsg(struct.Struct('<B'), 1, '{:02x}'.format),
}
for id in b'EC E1 E2 E3 E5 EI CE 1E 2E 3E 5E IE'.split():
    vmessages[id] = VMsg(struct.Struct('<B'), 1, '{:d}'.format)
for id in b'FC F1 F2 F3 F5 FI'.split():
    vmessages[id] = VMsg(struct.Struct('<H'), 2, '{:04x}'.format)
for id in b'cc c1 c2 c3 c5 ec e1 e2 e3 e5 qc q1 q2 a3 q5 1d 2d 3d 5d ' \
          b'1r 2r 3r 5r'.split():
    vmessages[id] = VMsg(struct.Struct('<h'), 2, '{:d}'.format)
for id in b'CP 1P 2P 3P 5P'.split():
    vmessages[id] = VMsg(struct.Struct('<f'), 4, '{:f}'.format)
for id in b'R1 R2 R3 R5 PC P1 P2 P3 P5'.split():
    vmessages[id] = VMsg(struct.Struct('<d'), 8, '{:f}'.format)
for id in b'rc r1 r2 r3 r5 pc p1 p2 p3 p5 DC D1 D2 D3 D5 cp 1p 2p 3p 5p'.split():
    vmessages[id] = VMsg(struct.Struct('<i'), 4, '{:d}'.format)
for id in b'pc p1 p2 p3 p5'.split():
    vmessages[id] = VMsg(struct.Struct('<I'), 4, '{:d}'.format)
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



def make_xds_str(fmtstruct, translator = {
        'f': '{:0.6e}','d': '{:0.15e}', 's': '{:s}',
        'B': '{:d}','b': '{:d}',        'H': '{:d}','h': '{:d}',
        'L': '{:d}','l': '{:d}',        'I': '{:d}','i': '{:d}',
        'q': '{:d}','Q': '{:d}',
    }):
    parts=[]
    for c in fmtstruct.format:
        if c in translator:
            parts.append(translator[c])
    parts[-1] = '{:02x}'
    return ' '.join(parts)

for k in messages:
    if messages[k].fmt == '':
        messages[k] = GMsgDef(messages[k].struct, messages[k].dtype, make_xds_str(messages[k].struct) )

# End module variable definitions
##############################################################################
def GREISParser(fp, skip_crlf=False, b_print=True):
    """ 
    Parse out fields within known GREIS messages
    skip_crlf will have the GREIS parser not yield garbage data that consists only of \n or \r\n
    b_print - if true, will print messages if data is unparseable
    """

    s_crc8 = struct.Struct('<B')

    for data in GREISReader(fp, skip_crlf):
        # TODO: validate checksums here
        if data.id in messages:
            # known fixed-length messages
            try:
                msgdef = messages[data.id]
                parsed = msgdef.dtype(*msgdef.struct.unpack(data.body))
                yield GREISMsgParsed._make(data + (parsed,))
            except struct.error:
                if b_print:
                    print("# unparseable: id={:s}; input data length={:d}; expected length={:d}".format(
                        data[0].decode(), len(data.body), msgdef.struct.size ))
                yield data
        elif data.id in vmessages:
            # for vmessages maybe we can do an iter_unpack?
            # known variable-length messages
            msgdef = vmessages[data.id]
            slen = len(data.body)-1

            try:
                fields = [x[0] for x in msgdef.type.iter_unpack(data.body[0:slen])]
                fields.append(s_crc8.unpack_from(data.body, slen)[0])
                fields = tuple(fields)
            except struct.error:
                if b_print:
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
        lenbuff = len(buffer)
        if lenbuff < 5:
            buffer += fp.read(5 - lenbuff)
        # if not enough data, quit
        if len(buffer) < 5:
            break

        # enforce message id restrictions
        b_msg_valid = is_header_valid(buffer)

        try:
            msglen = int(buffer[2:],16)
        except ValueError as e:
            b_msg_valid = False

        if not b_msg_valid:
            baddata.append(buffer[0])
            del buffer[0]
            # buffer = buffer[1:]
            continue

        msgbody = fp.read(msglen)
        # if there isn't any bad data, or it is just a line ending and we
        # are skipping bad data, then don't emit it.
        if not ((baddata == b'') or (skip_crlf and (baddata == b"\n" or baddata == b"\r\n"))):
            yield GREISMsg(b'??', b'???', baddata)
        baddata = bytearray()
        yield GREISMsg(bytes(buffer[0:2]), bytes(buffer[2:]), msgbody)
        buffer = bytearray()
    # Emit the last data
    # if there isn't any bad data, or it is just a line ending and we
    # are skipping bad data, then don't emit it.
    baddata += buffer
    if not ((baddata == b'') or (skip_crlf and (baddata == b"\n" or baddata == b"\r\n"))):
        yield GREISMsg(b'??',b'???', baddata)
    baddata = b''

# Pre-calculate rotation left by 2 for crc8
ROTL2 = tuple([((c << 2) | (c >> 6)) & 0xff for c in range(256)])

def crc8(data):
    #define ROT_LEFT(val) ((val << lShift) | (val >> rShift))
    res = 0

    #for c in bytearray(data):
    #    res = (((res << 2) | ( res >> 6)) & 0xff) ^ c
    #return ((res << 2) | ( res >> 6)) & 0xff
    for c in data:
        res = ROTL2[res] ^ c
    return ROTL2[res]

def is_header_valid(h):
    # Inline these comparisons for faster performance
    #b_msg_valid = is_headerchar(buffer[0]) and is_headerchar(buffer[1]) and \
    #    is_hexdigit(buffer[2]) and is_hexdigit(buffer[3]) and is_hexdigit(buffer[4])
    return ((48 <= h[0] <= 126) and
            (48 <= h[1] <= 126) and
            ((0x30 <= h[2] <= 0x39) or (0x41 <= h[2] <= 0x46)) and
            ((0x30 <= h[3] <= 0x39) or (0x41 <= h[3] <= 0x46)) and
            ((0x30 <= h[4] <= 0x39) or (0x41 <= h[4] <= 0x46))
           )

def is_headerchar(c):
    # b = ord(c) # python2
    return 48 <= c <= 126
def is_hexdigit(c):
    return (0x30 <= c <= 0x39) or (0x41 <= c <= 0x46)


def make_xds( id, data ):
    if id in messages:
        fmtstr = messages[id][2]
        return fmtstr.format(*data)
    elif id in vmessages:
        formatter = vmessages[id].fmt
        fields = [formatter(x) for x in data[0:-1]]
        # append CRC8 to fields
        return ' '.join(fields) + ' {:02x}'.format(data[-1])
    else: # pragma: no cover
        return ''

def test(args):
    LOGLEVEL=logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=LOGLEVEL, stream=sys.stdout)

    input_bxds = args.input
    msgcount = {}

    is_debug = logging.getLogger().isEnabledFor(logging.DEBUG)
    is_info = logging.getLogger().isEnabledFor(logging.INFO)

    with open(input_bxds, "rb") as fh:
        for ii, data in enumerate(GREISParser(fh, True)):
            if is_debug:
                logging.debug("greis: %r", (data[0], data[1], binascii.b2a_hex(data[2])))

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
                    logging.warning("Bad CRC asc (should be 0x%02x)", cs)
            else:
                cs = crc8(data[0] + data[1] + data[2][0:-1])
                if cs != data[2][-1]:
                    logging.warning("Bad CRC bin (should be 0x%02x)", cs)

            if args.nmax is not None and ii >= args.nmax:
                break

    print("Message totals: ")
    for k, v in sorted(msgcount.items(), key=by_value):
        print(k, ': ', v)


def by_value(item):
    # Sort in reverse order of size and forward by name
    return (-item[1], item[0])


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument('-i','--input',  help='Input jps file', required=True)
    parser.add_argument('--nmax', type=int, default=None, required=False, help='Max number of packets to process')
    parser.add_argument('-v', '--verbose', action="store_true", help='verbose output',
                        required=False)
    args = parser.parse_args()

    test(args)




if __name__ == "__main__":
    main()
