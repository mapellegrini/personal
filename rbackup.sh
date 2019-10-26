#!/bin/bash

#personal settings 
sourcehost="picard"
sourcedir="/mnt/data/bin"
targethost="troi" 
targetdir="/mnt/backup/picard/daily"
log="/tmp/rbackup.log" 

uname=$(whoami)
hname=$(hostname) 
scriptpath=${BASH_SOURCE%/*}/getmyextip.py
myextip=$($scriptpath)

if [ $hname == $sourcehost ] ; then
    echo "Source side backup initated" $(date)>> $log 
    ssh $targethost "echo $myextip > /tmp/$sourcehost" >> $log 2>&1
    rsync --archive --delete $sourcedir $uname@$targethost:$targetdir >> $log 2>&1 
    echo "Source side backup complete" $(date) >> $log
elif [ $hname == $targethost ] ; then
    echo "Target side backup initated" $(date)>> $log
    ssh sourcehost "echo $myextip > /tmp/$targethost"  >> $log 2>&1
    echo "Target side backup complete" $(date)>> $log
else
    echo "Backup aborted. Error - unknown host"  >> $log 2>&1
    exit
fi

