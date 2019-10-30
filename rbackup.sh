#!/bin/bash

#personal settings 
sourcehost="picard"
#sourcedirs="/mnt/data/ /mnt/data2/"  #actual mounts to be enabled later 
sourcedirs="/mnt/data/bin /mnt/data/career/job_search" #temporary test mounts:
targethost="troi"
targetmount="/mnt/externalusb" 
#targetdir=$targetmount"/daily/picard/"
targetdir=$targetmount"/onetime/picard/"
log="/tmp/rbackup.log" 

uname=$(whoami)
hname=$(hostname) 
scriptpath=${BASH_SOURCE%/*}/getmyextip.py
myextip=$($scriptpath)

if [ $hname == $sourcehost ] ; then
    tmounts=$(ssh $targethost cat "/proc/mounts")
    if echo $tmounts | grep -qs $targetmount ; then
	echo "Source side backup initated to @" $targethost ":" $targetdir $(date)>> $log 2>&1
	for sourcedir in $sourcedirs; do
	    echo "Backing up:" $sourcedir $(date) >> $log; 2>&1	
	    rsync --archive --delete $sourcedir $uname@$targethost:$targetdir >> $log 2>&1
	done
	ssh $targethost "echo $myextip > /tmp/$sourcehost" >> $log 2>&1	
	echo "Source side backup complete" $(date) >> $log
    else
	echo FALSE;
    fi
elif [ $hname == $targethost ] ; then
    echo "Target side backup initated" $(date)>> $log
    ssh sourcehost "echo $myextip > /tmp/$targethost"  >> $log 2>&1
    echo "Target side backup complete" $(date)>> $log
else
    echo "Backup aborted. Error - unknown host"  >> $log 2>&1
    exit
fi

