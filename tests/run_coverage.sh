#!/bin/bash

COV=coverage3

D0=`dirname $0`
DATADIR=$D0/out_cov
mkdir -p $DATADIR

rm -f $DATADIR/*.txt

$COV run ../server.py -h > /dev/null
$COV run -a ../nav.py -h > /dev/null

# ../nav_nmea
for FILE in ../bognss/JVD/greis.py ../bognss/NVT/nvt.py \
    ../nav_nvt.py ../nav_jvd.py
do
    $COV run -a $FILE -h > /dev/null
done


$COV run -a ../bognss/NVT/nvt.py -i data/ICP9_F03_TOT3_JKB2s_X07a_AVNnp1_bxds > /dev/null
$COV run -a ../bognss/JVD/greis.py -i data/ICP9_F03_TOT3_JKB2s_X07a_AVNnp1_bxds > /dev/null


$COV run -a ../possim.py > /dev/null

# Generate some NMEA
$COV run -a ../utils/gen_nmea.py --time 5. > $DATADIR/nmea.txt
# Parse it
cat $DATADIR/nmea.txt | $COV run -a  ../nav_nmea.py > $DATADIR/parsed.txt


# Cause a parse error with a partial packet (like might happen on startup)
tail -c +9 $DATADIR/nmea.txt > $DATADIR/partial_nmea.txt
cat $DATADIR/partial_nmea.txt | $COV run -a ../nav_nmea.py > $DATADIR/parsed_partial.txt

# TODO: add simulator
# $COV run -a ../utils/server.py --format nmeasim
# $COV run -a ../utils/server.py --format nvtsim
# $COV run -a ../utils/server.py --format jvdsim
