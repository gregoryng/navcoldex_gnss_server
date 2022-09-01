#!/usr/bin/env python3

""" Routines for decoding a Novatel data file. such as from SPAN 
You can import this routine and then easily read Novatel packets out,
filtering for the message IDs that you are interested in, or demultiplexing
message streams.

Open question:
Is the crc considered part of the payload or part of the transport stream?
That is, should we check the checksum in the NovatelReader or in the NovatelParser?

In normal circumstances it would be checked as part of the NovatelReader, but it
is defined in the data fields...

# TODO: error-correction-only script
- when searching for header, inspect for bits that have a very close hamming distance to
0xaa 44 12 and 0xaa4413, and try speculatively treating these bits as a header.


"""


from collections import namedtuple
import struct
import logging
import binascii
import itertools
from array import array
import os
import subprocess

####################################
# Logging severity configuration
G_LOGLEVEL_UNKNOWN_MSG=logging.WARNING

###################################



# Message definition
MsgDef = namedtuple('MsgDef','struct nt fmtstr')
NVTMsg = namedtuple('NVTMsg','msglen header headerbytes msgbytes parsed')
NVT_Msg140 = namedtuple('NVT_Msg140', 'cts dfreq psr adr stddev_psr stddev_adr prnslot locktime cno glofreqnum resvd1')

MsgDef_NVT0x13 = MsgDef._make((struct.Struct("<BHHL"), 
    namedtuple('NVT0x13H','msglen msgid gnssweek gnssmsec'), 
    "{:d} {:d} {:d} {:d}"))

MsgDef_NVT0x12 = MsgDef._make((struct.Struct('<BHBBHHBBHLLHH'), 
    namedtuple('NVT0x12H','hlen msgid msgtype portaddr msglen seq idletime timestat gnssweek gnssmsec rxstatus resvd1 rxswver'), 
    "{:d} {:d} {:02x} {:02x} {:d} {:d} {:d} {:02x} {:d} {:d} {:08x} {:04x} {:d}"))


gps_offset = 315964800
gps_week_secs = 604800

# Novatel message definitions

messages = {

8: MsgDef._make((
    # previously:
    #struct.Struct('<ddddddddLLddLLll'),
    #namedtuple('IONUTC', 'a0 a1 a2 a3 b0 b1 b2 b3 utc_wn tot A0 A1 wn_lsf dn deltat_ls deltat_lsf'),
    # In OM-20000129_OEM6 firmware reference Rev 10, page 498-499, it has the following definition
    struct.Struct('<ddddddddLLddLLllLL'),
    namedtuple('IONUTC', 'a0 a1 a2 a3 b0 b1 b2 b3 utc_wn tot A0 A1 wn_lsf dn deltat_ls deltat_lsf resvd1 crc'),
    '')),

41 : MsgDef._make((
    struct.Struct('<LLL30s30s30sL'), 
    namedtuple('RAWEPHEM','prn ref_week ref_secs subframe1 subframe2 subframe3 crc'),'')),

42: MsgDef._make(( # same as BESTGPSPOS
    struct.Struct('<LLdddfLfff4sffBBBBBBBBL'), 
    namedtuple('BESTPOS', \
        'sol_status pos_type lat lon hgt undulation datum_id latsigma lonsigma hgtsigma ' + \
        'stn_id diff_age sol_age num_obs num_gpsl1 num_l1 num_l2 resvd1 resvd2 resvd3 resvd4 crc'),
        '{:d} {:d} {:0.9f} {:0.9f} {:0.4f} {:0.4e} {:d} {:0.5f} {:0.5f} {:0.3f} {!r} {:f} {:f} {:d} {:d} {:d} {:d} {:d} {:d} {:d} {:d} {:08x}')),


99: MsgDef._make((
    struct.Struct('<LLffdddfL'),
    namedtuple('BESTVEL', 'sol_stat vel_type latency age hor_spd trk_gnd vert_spd resvd1 crc'), '')),

101: MsgDef._make((
     struct.Struct('<LdddLBBBBLL'),
     namedtuple('TIME', 'clk_stat offset offset_stdev utc_offset utc_year utc_montht utc_day utc_hour utc_min utc_ms utc_stat'), '')),
     

140 : MsgDef._make((None, None, '')),

263 : MsgDef._make((
    struct.Struct('<LddddLL'), 
    namedtuple('INSATT','gnssweek gnsssec roll pitch azimuth status crc'), 
    '{:d} {:0.4f} {:f} {:f} {:f} {:08x} {:08x}')),

268 : MsgDef._make((
    struct.Struct('<LdllllllllL'), 
    namedtuple('RAWIMU','gnssweek gnsssec imustatus ' + \
                        'z_acc_raw y_acc_raw x_acc_raw ' + \
                        'z_spin_raw y_spin_raw x_spin_raw crc'),'')),

320 : MsgDef._make((
    #struct.Struct('<Ld9d9d9dL'),
    struct.Struct('<LddddddddddddddddddddddddddddL'),
    namedtuple('INSCOVS','gnssweek gnsssec ' + \
                         'pxx pxy pxz pyx pyy pyz pzx pzy pzz ' + \
                         'axx axy axz ayx ayy ayz azx azy azz ' + \
                         'vxx vxy vxz vyx vyy vyz vzx vzy vzz ' + \
                        'crc'),'')),

325 : MsgDef._make((
    struct.Struct('<LdLllllllL'),
    namedtuple('RAWIMUS','gnssweek gnsssec imustatus ' + \
                         'z_acc_raw y_acc_raw x_acc_raw ' + \
                         'z_spin_raw y_spin_raw x_spin_raw crc'),
    '{:d} {:0.4f} {:08x} {:d} {:d} {:d} {:d} {:d} {:d} {:08x}')),

423 : MsgDef._make((
    struct.Struct('<LLdddfLfff4sffBBBBBBBBL'), 
    namedtuple('BESTGPSPOS', \
        'sol_status pos_type lat lon hgt undulation datum_id latsigma lonsigma hgtsigma ' + \
        'stn_id diff_age sol_age num_obs num_gpsl1 num_l1 num_l2 resvd1 resvd2 resvd3 resvd4 crc'),
        '{:d} {:d} {:0.9f} {:0.9f} {:0.4f} {:0.4e} {:d} {:0.5f} {:0.5f} {:0.3f} {!r} {:f} {:f} {:d} {:d} {:d} {:d} {:d} {:d} {:d} {:d} {:08x}')),
    

231 : MsgDef._make((
    struct.Struct('<LddddLL'), 
    namedtuple('MARKTIME','gnssweek gnsssec rxoffset rxoffset_std utc_offset clockstatus crc'),'')),
616 : MsgDef._make((
    struct.Struct('<LddddLL'), 
    namedtuple('MARK2TIME','gnssweek gnsssec rxoffset rxoffset_std utc_offset clockstatus crc'),'')),

507 : MsgDef._make((
    struct.Struct('<LddddddddddLL'), 
    namedtuple('INSPVA','gnssweek gnsssec lat lon hgt vn ve vu roll pitch azimuth status crc'),
    '{:d} {:0.4f} {:0.9f} {:0.9f} {:0.4f} {:0.3f} {:0.3f} {:0.3f} {:0.3f} {:0.3f} {:0.3f} {:08x} {:08x}')),
508 : MsgDef._make((
    struct.Struct('<LddddddddddLL'), 
    namedtuple('INSPVAS', 'gnssweek gnsssec lat lon hgt vn ve vu roll pitch azimuth status crc'),
    '{:d} {:0.4f} {:0.9f} {:0.9f} {:0.4f} {:0.3f} {:0.3f} {:0.3f} {:0.3f} {:0.3f} {:0.3f} {:08x} {:08x}')),

642 : MsgDef._make((struct.Struct('<ddddddL'), 
    namedtuple('VEHICLEBODYROTATION','xang yang zang xunc yunc zunc crc'), '')),


1068: MsgDef._make((struct.Struct('<LddddddddddIL'), # exact same message type as INSPVAS
      namedtuple('MARK2PVA', 'gps_week gps_seconds latitude longitude height vel_north vel_east vel_up roll pitch azimuth status crc'), '')),
1146: MsgDef._make((
       struct.Struct('<L12sLLL'),
       namedtuple('LOGFILESTATUS','FileState FileName FileSize Media crc'),'')),


# TODO: this has a variable number of entries...
1270 : MsgDef._make((None,None,'')),
#1270 : MsgDef._make((struct.Struct('<ddddddL'), 
#    namedtuple('IMUTOANTOFFSETS','imuorientation  crc'), '')),
}
messages[506] = messages[99] # BESTGPSVEL is same as BESTVEL


# From OM-20000144UM (SPAN on OEM6 firmware reference)
oem6_rxstatus_flags = (
(0, 0x00000001, "Error flag", "No error","Error"),
(1, 0x00000002, "Temperature status", "Within specifications", "Warning"),
(2, 0x00000004, "Voltage supply status", "OK", "Warning"),
(3, 0x00000008, "Antenna power status", " Powered", "Not powered"),
(4, 0x00000010, "LNA Failure", "0","1"),
(5, 0x00000020, "Antenna open flag", "OK", "Open"),
(6, 0x00000040, "Antenna shorted flag", "OK", "Shorted"),
(7, 0x00000080, "CPU overload flag", "No overload", "Overload"),
(8, 0x00000100, "COM1 buffer overrun flag", "No overrun", "Overrun"),
(9, 0x00000200, "COM2 buffer overrun flag", "No overrun", "Overrun"),
(10, 0x00000400, "COM3 buffer overrun flag", "No overrun", "Overrun"),
(11, 0x00000800, "Link overrun flag", " No overrun", " Overrun"),
(12, 0x00001000, "Reserved", "0","1"),
(13, 0x00002000, "Aux transmit overrun flag", "No overrun","Overrun"),
(14, 0x00004000, "AGC out of range", "0","1"),
(15, 0x00008000, "Reserved", "0","1"),
(16, 0x00010000, "INS Reset", "No Reset", "INS filter has reset"),
(17, 0x00020000, "Reserved", "0","1"),
(18, 0x00040000, "Almanac flag/UTC known", "Valid","Invalid"),
(19, 0x00080000, "Position solution flag", "Valid","Invalid"),
(20, 0x00100000, "Position fixed flag", "Not fixed", "Fixed"),
(21, 0x00200000, "Clock steering status", "Enabled","Disabled"),
(22, 0x00400000, "Clock model flag", "Valid","Invalid"),
(23, 0x00800000, "External oscillator locked flag", "Unlocked","Locked"),
(24, 0x01000000, "Software resource", " OK", "Warning"),
(25, 0x02000000, "Reserved", "0","1"),
(26, 0x04000000, "Bit 26", "0","1"),
(27, 0x08000000, "Bit 27", "0","1"),
(28, 0x10000000, "Bit 28", "0","1"),
(29, 0x20000000, "Auxiliary 3 status event flag", "No event", "Event"),
(30, 0x40000000, "Auxiliary 2 status event flag", "No event", "Event"),
(31, 0x80000000, "Auxiliary 1 status event flag", "No event", "Event"),
)





# TODO: make this string able to reorder the fields...
# TODO: make this xds string generate the correct result for a 9d string
def make_xds_str(fmtstr,translator = {
        'f': '{:0.6e}','d': '{:0.15e}', 's': '{!r}', 'c': '{!r}',
        'B': '{:d}','b': '{:d}',        'H': '{:d}','h': '{:d}',
        'L': '{:d}','l': '{:d}',        'I': '{:d}','i': '{:d}',
        'q': '{:d}','Q': '{:d}',
    }):
    parts=[]
    #logging.debug("Translation string: {:s}".format(fmtstr))
    for c1 in fmtstr:
        try:
            c = chr(c1) # python3.5
        except TypeError:
            c = c1

        if c in '!<>0123456789':
            continue
        elif c in translator:
            parts.append(translator[c])
        else: #pragma: no cover
            logging.debug("character '%s' not in translation table", c)
    # Always make the CRC field hex by default
    parts[-1] = '{:08x}'
    return ' '.join(parts)
    

def make_xds( id, data ):
    if id in messages:
        fmtstr = messages[id][2]
        return fmtstr.format(*data)
    else:
        return ''

def make_xds_header(header):
    # Get the header type and prepend the corect header information
    if type(header).__name__ == 'NVT0x12H':
        return MsgDef_NVT0x12.fmtstr.format(*header)
    elif type(header).__name__ == 'NVT0x13H':
        return MsgDef_NVT0x13.fmtstr.format(*header)
    else: # pragma: no cover
        return '?'



def CRC32Value( ii, CRC32_POLYNOMIAL):
    ulCRC=ii
    #for ($jj=8; $jj > 0; $jj-- ) {
    for jj in (8,7,6,5,4,3,2,1):
        if ( ulCRC & 1 ):
            ulCRC = ( ulCRC >> 1 ) ^ CRC32_POLYNOMIAL;
        else:
            ulCRC >>= 1
    return ulCRC


def GetCRCTable(CRCPOLYNOMIAL=0xEDB88320):
    #return map( CRC32Value($_, $CRCPOLYNOMIAL), 0..255 );
    return tuple( [ CRC32Value(x, CRCPOLYNOMIAL) for x in range(256) ] )

#/* --------------------------------------------------------------------------
#Calculates the CRC-32 of a block of data all at once
#-------------------------------------------------------------------------- */

def CalculateBlockCRC32 (sBuffer, ulCRC=0, crctable=GetCRCTable()):
    (ulTemp1, ulTemp2) = (0,0)
    #for c in (unpack("C*", ucBuffer)) {
    #for c in array('B',sBuffer):
    for c in bytearray(sBuffer):
        ulTemp1 = ( ulCRC >> 8 ) & 0x00FFFFFF
        ulTemp2 = crctable[ (ulCRC ^ c) & 0xff ]
        ulCRC = ulTemp1 ^ ulTemp2

    return ulCRC

def numberOfSetBits(i):
    # Count and return the number of bits set in a 32-bit value.
    i = i - ((i >> 1) & 0x55555555)
    i = (i & 0x33333333) + ((i >> 2) & 0x33333333)
    return (((i + (i >> 4) & 0xF0F0F0F) * 0x1010101) & 0xffffffff) >> 24

def CountCRC32_ErrorBits(crc1, crc2):
    return numberOfSetBits(crc1 ^ crc2)

def CalculatePacketCRC32(sBuffer):
    # assume last 4 bytes are CRC
    (crc_msg,) = struct.unpack('<L', sBuffer[-4:])
    crc_calc = CalculateBlockCRC32( sBuffer[0:-4] )
    return (crc_calc, crc_msg, crc_calc == crc_msg)

def hamming_dist(s1, s2):
    len_s1 = len(s1)
    if len_s1 != len(s2):
        return None
    d = 0
    for i in range(len_s1):
        # TODO: use a numberOfSetBits function that is tuned for 8 bits.
        d += numberOfSetBits(s1[i] ^ s2[i])

    return d



def NovatelParser(fp, msgids=None, b_calc_crc=False, b_correct_crc=False):
    global G_LOGLEVEL_UNKNOWN_MSG

    # If there is a CRC error, make the first occurrence an info, and the subsequent
    # ones a warning.
    num_badcrc = 0
    num_unparseable = 0

    stats = {}
    crctab = GetCRCTable()

    # Max size of packet to perform ECC on
    ecc_msg_max_size = 3000

    # Pre-load the xds format strings for any that are not defined.
    for k,v in messages.items():
        if v.fmtstr == '' and v[0] is not None:
            messages[k] = v._replace( fmtstr=make_xds_str(v[0].format ) )

    for data in NovatelReader(fp):
        (msglen, header, headerbytes, msgbytes) = data
        if msglen == 0:
            logging.debug("Trash (%d): %s", len(msgbytes), msgbytes.hex() )
            continue

        # If we've been provided with a whitelist, use it.
        if msgids is not None and not(header.msgid in msgids):
            continue

        if header is None:
            continue

        msgspec = messages.get(header.msgid)

        parsed = None
        if msgspec is not None:

            b_badcrc=False
            if b_calc_crc:
                if len(msgbytes) >= 4:
                    (crc_msg,) = struct.unpack('<L', msgbytes[-4:])

                    crc_calc = CalculateBlockCRC32( headerbytes, 0, crctab )
                    crc_calc = CalculateBlockCRC32( msgbytes[0:-4], crc_calc, crctab )
                else:
                    crc_calc = 1
                    crc_msg = 0
            
                # my $crc_calc = CalculateBlockCRC32($raw_header . $buff, \@crctable);
                if crc_msg != crc_calc:
                    b_badcrc=True
                    loglevel = logging.INFO if num_badcrc == 0 else logging.WARNING
                    logging.log(loglevel, "msg={0.msgid:04d} week={0.gnssweek:d} msec={0.gnssmsec:d}: "
                                "CRC mismatch, crc={1:08x} calc={2:08x} len={3:d}. "
                                "{4:d} previous occurrences".format( 
                                header, crc_msg, crc_calc, len(headerbytes) + len(msgbytes), num_badcrc ))
                    num_badcrc += 1


            if msgspec[0] is not None and msgspec[1] is not None:
                # known messages
                try:
                    parsed = msgspec[1]._make( msgspec[0].unpack(msgbytes) )
                except struct.error:
                    loglevel = logging.INFO if num_unparseable == 0 else logging.WARNING
                    logging.log(loglevel, "unparseable: id={:04d}; input data length={:d}; "
                                "expected length={:d}; {:d} previous occurrences".format(
                    header.msgid, len(msgbytes), msgspec[0].size, num_unparseable ))
                    yield NVTMsg._make(data + (None,))
                    num_unparseable += 1
                    continue
            else:
                # This message type is known, but not parsed.
                logging.debug("msg={0.msgid:04d} week={0.gnssweek:d} msec={0.gnssmsec:d}: ignored".format(header))


            if not b_badcrc:
                yield NVTMsg._make(data + (parsed,))
        else:
            # everything else just pass it through.
            logging.log(G_LOGLEVEL_UNKNOWN_MSG, "Unknown message id {:d}".format(header.msgid))
            yield NVTMsg._make(data + (None,))



def NovatelReader(fp):
    '''
    Reads a Novatel standard message stream as defined in SPAN on OEM6 reference guide
    
    There is no guarantee that the binary file's start will be aligned with
    the start of a data packet. This scans through the file until it
    finds a valid Novatel header

    Every standard binary message begins with 0xAA 0x44 0x12, then length of header
    
    # See respective yield statements (below) for information about how to differentiate
    # std headers, ascii, and binary headers.
    # TODO: Novatel Reader return named tuple
    
    '''

    b_allow_ascii = False

    buffer=b''
    baddata=b''
    header1 = b'\xaa\x44\x12' # long header
    header2 = b'\xaa\x44\x13' # short header

    while True:
        b_msg_valid=True
        header=None
        # We read 4 characters instead of 3 to reduce the number of calls to
        # fp.read for the long header case
        lb = len(buffer)
        if lb < 4:
            buffer += fp.read( 4 - lb )
        # if not enough data, quit
        if len(buffer) < 4:
            break

        # Check whether this is a recognized header
        if buffer[0:3] == header1: # long header
            headerlen = int(buffer[3])
            if headerlen <= 4:
                # NOTE: consider possibility that this byte is corrupted.
                b_msg_valid=False
            else:
                # Append the first character to the buffer
                buffer += fp.read(headerlen-4)
                #hbuffer = buffer[3] + fp.read(headerlen-4)
                try:
                    header  = MsgDef_NVT0x12.nt._make(MsgDef_NVT0x12.struct.unpack(buffer[3:]))
                except struct.error as e:
                    logging.warning("hbuffer length: %d, expected %d", len(buffer[3:]), MsgDef_NVT0x12.struct.size)
                    b_msg_valid = False
                    #buffer += hbuffer[1:]
            
        elif buffer[0:3] == header2: # short header
            # Append the first character to the buffer
            #hbuffer = buffer[3] + fp.read(8)
            buffer += fp.read(8)
            try:
                header  = MsgDef_NVT0x13.nt._make(MsgDef_NVT0x13.struct.unpack(buffer[3:]))
            except struct.error as e:
                logging.warning("hbuffer length: {:d}, expected {:d}".format(len(buffer[3:]), MsgDef_NVT0x13.struct.size) )
                #buffer += hbuffer[1:]
                b_msg_valid = False
        elif b_allow_ascii and (buffer[0] == b'#' or buffer[0] == b'%'): # ascii long/short string (relatively untested)
            # WARNING: this has not been tested
            # Dump an ascii string
            logging.debug("ASCII msg")
            line = buffer + fp.readline()
            buffer = b''
            # Ascii data uses the length of the line (> 0) for the header, and "None" for the header.
            yield len(line), None, None, line
            continue
        else:
            # TODO: look for similar hamming distance?
            b_msg_valid = False

        # If the message is invalid, kick out the first character and start over
        if not b_msg_valid:
            assert len(buffer[0:1]) == 1
            baddata += buffer[0:1]
            buffer = buffer[1:]
            continue
        
        # Add 4 bytes for the CRC
        msgbytes = fp.read(header.msglen+4)
        if baddata != b'':
            # Garbage data has 0 as value for the msglen, and None for the header
            yield (0, None, None, baddata)
            baddata = b''

        # Real data has valid data for msglen and header.
        #headerbytes = buffer #buffer[0:3] + hbuffer
        # buffer is the headerbytes
        yield (header.msglen, header, buffer, msgbytes)

        buffer = b''
    # yield bad data at the end
    if buffer != b'':
        baddata += buffer
        buffer = b''
    if baddata != b'':
        # Garbage data has 0 as value for the msglen, and None for the header
        yield (0, None, None, baddata)
        baddata = b''



def parse_nvt_msg140(buffer):
    # Parse Novatel message 140 (RANGECMP)
    # Number of observations is usually < 128, so zero out nobs high order bits.
    # Note: resvd bits usually 0x0000, glonass frequency number 0-3, but is a 5-bit field
    # Slot numbers can be constrained due to sats tracked, which should be GPS only for this unit. (1-32)
    # C/No is constrained to 20-51?
    if buffer is None:
        buffer = binascii.a2b_hex(
"aa44121c8c0000405c0200007cb4c107c81e8c05000000009196ba3519000000049c10082b2707\
709fe85a0abe2bacb2f117b22ec00200000b3c3001e392056088e85a0a321e1fb3f417892c2002\
0000249c1008f65cf1cf49884a0bb4d14495e116082f800200002b3c30013a98f46f2e884a0b81\
2d78b8f516682ca0010000449c10189a69f66f0659ac0a93562dfd70133317200300004b3c3011\
7c87f84fef58ac0ad1d56f8983131c1760020000649c1008944c0330c01e0a0b176094bf5019a7\
2a400300006b3c30011e920290c61e0a0bcc5770d96219902a0003000084940008169c0de0c88f\
450bb7ad8898f8092100e0010000a49c100841b304b0458bea09c0887bfc6006dc2d40030000ab\
3c300197a903f0528bea0906c0a2ec6206c82b00030000c49c100829c00dc057e7aa0a801d20fe\
5002351940030000cb3c3001fdb60a8035e7aa0add042d8a92023519c0020000e49c10180b1bf1\
2ff65ef90b69bd6ba2f60e9e0120020000eb3c3011e164f49fe85ef90bd428fadef80e8201e001\
0000249d100834a101b09000e00ae7073fdb501fb52e600300002b3d3001184501b07500e00aea\
4cffee631f572c80020000449d1008293cf0cf7c57590bd46a8a8bb1113c11e00200004b3d3001\
2fb7f30f8057590b2a9ae3b0d5113c11e0010000849d10183a64facfe00be10ab0758fda400ca2\
2da00300008b3d301137a1fb2fcc0be10a5b7776ee430cc72bc0020000e49d10082189f58fc6e7\
800acba2b699c103c72de0020000eb3d300192d8f74fd0e7800a8134ac9fe303c62b8002000044\
9e15589c9d03b05e1a231114ca33be70c30b2b400300004b9e354242d10210561a2311138271ba\
70c30b2b600300000e7b1f08" )
        logging.info("Data length: %d", len(buffer) )
        print("Data length2: {:d}".format(len(buffer)))


    headerbytes = buffer[3:(3+MsgDef_NVT0x12.struct.size)]
    msgbytes    = buffer[(3+MsgDef_NVT0x12.struct.size):]
    header = MsgDef_NVT0x12.nt._make(MsgDef_NVT0x12.struct.unpack(headerbytes))

    logging.debug("msg140: header   %s", str(header))
    logging.debug("msg140: msgbytes (%d) %s", len(msgbytes),  msgbytes.hex())
    s_int = struct.Struct('<L')
    
    (nobs,) = s_int.unpack(msgbytes[0:4])
    logging.debug("msg140: nobs={:d}".format(nobs) )
    # TODO: figure out nobs from message length
    if nobs > 100:
        nobs0=nobs
        nobs = (len(msgbytes)-4)/24
        logging.info("Suspiciously high nobs value ({0:d}/0x{0:08x}). Using {1:d}".format(nobs0, nobs ) )
        #assert(nobs < 100) # usually less than this.


    for (i,j) in enumerate(range(4, len(msgbytes)-4, 24) ):
        rangelog_data = msgbytes[j:(j+24)]

        logging.debug("msg140: rangelog %2d bin %s", i, rangelog_data.hex())

        if len(rangelog_data) != 24:
            logging.debug("msg140: rangelog %2d too short (len=%d)", i, len(rangelog_data))
            break

        
        # Channel tracking status (bits 0-31, 32 bits)
        cts   = s_int.unpack(rangelog_data[0:4] )[0]
        # Doppler frequency (bits 32-59, 28 bits)
        dfreq = float(s_int.unpack( rangelog_data[4:8] )[0] & 0x0fffffff ) / 256.0
        # Pseudorange (PSR) (bits 60-95, 36 bits)
        psr_low  = int(rangelog_data[7])
        psr_high = s_int.unpack( rangelog_data[8:12] )[0] & 0x0fffffff
        psr      = (float(psr_low) + float(psr_high) * 256.0) / 128.0
        # ADR (bits 96-127, 32 bits)
        adr   = float(s_int.unpack( rangelog_data[12:16])[0] ) / 256.0
        # StdDev-PSR (128-131, 4 bits) TODO: fully decode and confirm high/low order
        stddev_psr = rangelog_data[16] & 0x0f
        # StdDev-ADR (132-135, 4 bits) # TODO: confirm high/low order
        stddev_adr = float((( rangelog_data[16] & 0xf0) >> 4) + 1) / 512.0
        # PRN/Slot (136-143, 8 bits)
        prnslot    = rangelog_data[17]
        # Lock Time (144-164, 21 bits)
        locktime   = float(s_int.unpack(rangelog_data[18:22])[0] & 0x001fffff) / 32.0
        # C/No (bits 165-169, 5 bits) # TODO: finish decoding
        cno        = struct.unpack('<H', rangelog_data[20:22])[0]
        # GLONASS Frequency number (bits 170-175, n+7 bits?)
        glofreqnum = rangelog_data[21] # & mask
        #
        resvd1     = struct.unpack('<H', rangelog_data[22:])[0]


        data = NVT_Msg140._make( (cts, dfreq, psr, adr, stddev_psr, stddev_adr, prnslot, locktime, cno, glofreqnum, resvd1) )
        fmtstr = "cts={0.cts:08x} dfreq={0.dfreq:0.7f} psr={0.psr:0.3f} adr={0.adr:0.8f} std_psr=0x{0.stddev_psr:x} std_adr={0.stddev_adr:f} prnslot={0.prnslot:d} locktime={0.locktime:f} C/No={0.cno:04x} glofreqnum={0.glofreqnum:d} resvd={0.resvd1:04x}"
        logging.debug("msg140: rangelog {:2d} dat {:s}".format(i, fmtstr.format(data)) )
    

def bo_avnnp(input_bxds, outdir,messages, overwrite, b_calc_crc=False,b_correct_crc=False):
    """ Write a series of xds files into outdir, from data in input_bxds
    Optionally, choose a subset of messages to write xds files for.  messages
    is a sequence (list or tuple) of message IDs to be included.  To write
    all messages, set messages = None.  To write no message, set messages = []
    """
    dict_ofh={}
    # if messages is not set, then just write all messages.
    # (if messages is the empty set, write no messages)
    set_msgs = None if messages is None else frozenset(messages)

    fpos1=0
    with open(input_bxds,"rb") as fh:
        #msgids=None, b_calc_crc=False, b_correct_crc=False):
        for data in NovatelParser(fh, msgids=None, b_calc_crc=b_calc_crc, b_correct_crc=b_correct_crc):
            id = data.header.msgid

            if data.msglen > 0 and data.parsed is not None:
                xhead = make_xds_header(data.header)
                xds = make_xds( id, data.parsed )
                logging.debug("msg: %s %s", str(data.header), xds)

                if set_msgs is None or id in set_msgs:
                    if id not in dict_ofh:
                        ofn = os.path.join(outdir,"xds.{:04d}".format(id))
                        if os.path.exists(ofn) and not overwrite:
                            raise Exception("Output file {:s} already exists. Use --overwrite flag to overwrite this file.".format(ofn))
                        os.makedirs(outdir, exist_ok=True)




                        dict_ofh[id] = open(ofn,"wt")
                        logging.info("Writing breakout %s", ofn)
                    dict_ofh[id].write(xhead + ' ' + xds + "\n")
            else:
                logging.debug(str(data))

    # Close in a repeatable order
    for id in sorted(dict_ofh):
        dict_ofh[id].close()



def test(args):
    import time
    t0 = time.time()
    stats = {}
    # TODO: make rec a namedtuple in NovatelParser
    with open(args.input,'rb') as f:
        for i,rec in enumerate(NovatelParser(f, args.message, args.crc, args.correct)):
            if rec.parsed is not None:
                xds = make_xds( rec.header.msgid , rec.parsed )
            else:
                xds = '?'

            xhead = make_xds_header( rec.header )

            # prepend the header
            print('#' + xhead, xds)

            if rec.header.msgid == 140:
                parse_nvt_msg140( rec.headerbytes + rec.msgbytes )

            # Increment stats counter
            stats[rec.header.msgid] = stats.get(rec.header.msgid,0) + 1

            if args.limit is not None and i >= args.limit:
                break

        filesize = f.tell()

    logging.info('Message count:')
    logging.info(repr(stats))

    dt = max(time.time() - t0, 0.01)


    logging.info("Elapsed time: %0.2f sec, processing rate %0.2f MB/s", dt, filesize/1024/1024/dt)





if __name__ == "__main__":
    import argparse
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument('-c','--crc',  action="store_true", help='Compute CRCs and reject if bad CRC',
                        required=False)
    parser.add_argument('--correct',  action="store_true", help='Attempt to correct CRC errors',
                        required=False)
    parser.add_argument('--maxbiterrors', type=int, default=1, help='Max number of bit errors to correct',
                        required=False)
    parser.add_argument('--profile',  action="store_true", help='Profile code',
                        required=False, default="")
    parser.add_argument('-v','--verbose',  action="store_true", help='Verbose output',
                        required=False)
    parser.add_argument('--limit', type=int, help='Max number of records to process.',
                        required=False, default=None)
    parser.add_argument('-m','--message', type=int, action='append',help='Message IDs to return.  Skip all others', default=[])
    parser.add_argument('-i','--input',  help='Input directory or file',
                        required=False, default="")
    parser.add_argument('-o','--output', help='Output directory or file',
                        required=False)
    args = parser.parse_args()

    loglevel = logging.DEBUG if args.verbose else logging.WARNING

    logging.basicConfig(level=loglevel, stream=sys.stdout, format="nvt: [%(levelname)7s] %(message)s")

    args.message = frozenset(args.message) if len(args.message) > 0 else None









    test(args)



