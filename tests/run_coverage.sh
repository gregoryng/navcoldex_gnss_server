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
cat $DATADIR/nmea.txt | $COV run -a  ../server.py --format nmeasim --timeout 3 > $DATADIR/parsed_nmea.txt
$COV run -a ../server.py --format sim --timeout 3
$COV run -a  ../server.py --format jvdsim --timeout 3 > $DATADIR/parsed_jvd.txt
$COV run -a  ../server.py --format nvtsim --timeout 3 > $DATADIR/parsed_nvt.txt


# Cause a parse error with a partial packet (like might happen on startup)
tail -c +9 $DATADIR/nmea.txt > $DATADIR/partial_nmea.txt
cat $DATADIR/partial_nmea.txt | $COV run -a ../nav_nmea.py > $DATADIR/parsed_partial.txt


# Run the server and initiate a connection
$COV run -a ../server.py --format nvtsim --timeout 10 > $DATADIR/nvtsim_conn.txt &
PID="$!"
sleep 1
nc localhost 4063 &
# Have netcat wait for up to 2 seconds for a the connection to succeed, then
# run for up to 5 seconds before quitting, so that we break the connection
# and run the code that recycles the connection
#timeout 5s nc -w 2 localhost 4063
#timeout 5s nc -w 2 localhost 4063 &
wait $PID
echo "$COV report -m"
