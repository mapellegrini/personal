#!/bin/bash

#personal settings 
sourcehost="picard"
sourcedirs="/mnt/data /mnt/data2 /etc/" #temporary test mounts:
rtargethost="troi"
rtargetmount="/mnt/externalusb" 
rtargetdir=$rtargetmount"/daily/"
log="/tmp/rbackup.log" 

uname=$(whoami)
hname=$(hostname) 
scriptpath=${BASH_SOURCE%/*}/getmyextip.py
myextip=$($scriptpath)

if [ $hname == $sourcehost ] ; then
    tmounts=$(ssh $rtargethost cat "/proc/mounts")
    if echo $tmounts | grep -qs $rtargetmount ; then
	echo "Source side backup initated to @" $rtargethost ":" $rtargetdir $(date)>> $log 2>&1
	for sourcedir in $sourcedirs; do
	    echo "Backing up:" $sourcedir $(date) >> $log; 2>&1	
	    rsync --archive --delete $sourcedir $uname@$rtargethost:$targetdir >> $log 2>&1
	done
	ssh $rtargethost "echo $myextip > /tmp/$sourcehost" >> $log 2>&1	
	echo "Source side backup complete" $(date) >> $log
    else
	echo FALSE;
    fi
elif [ $hname == $rtargethost ] ; then
    echo "Target side backup initated" $(date)>> $log
    ssh sourcehost "echo $myextip > /tmp/$rtargethost"  >> $log 2>&1
    echo "Target side backup complete" $(date)>> $log
else
    echo "Backup aborted. Error - unknown host"  >> $log 2>&1
    exit
fi

