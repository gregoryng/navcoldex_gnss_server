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


$COV run -a ../possim.py > /dev/null

# Generate some NMEA
$COV run -a ../utils/gen_nmea.py --time 5. > $DATADIR/nmea.txt
# Parse it
cat $DATADIR/nmea.txt | $COV run -a  ../nav_nmea.py > $DATADIR/parsed.txt
