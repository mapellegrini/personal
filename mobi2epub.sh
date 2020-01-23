#!/bin/bash

display_usage() {
  echo "Usage: mobi2epun.sh [-h][-b][-s <string>]"
  echo ""
  echo "Converts a directory containing .mobi files into .epub files"
  echo ""
  echo "-h, --help        Show this help message and exit"
  echo "-s,               The directory containing .mobi files to be converted. "
  echo "-d,               The destination directory. If none is given, will default to /tmp."
}

#sdir=""
ddir="/tmp/" 
verbose="False"

while getopts "hvs:d:" opt; do #variables that take an argument are followed by a colon 
  case ${opt} in
    h | \? | help )
      display_usage; 
      exit 0 
      ;;
    v ) 
      verbose="True"
      ;;
    s )
      sdir=$OPTARG
      ;;
    d )
      ddir=$OPTARG
    esac
done


found=$(which ebook-convert) 
if [ -z $found ] 
then
    echo "Error: Could not find ebook-convert"
    exit 1
fi 


lchar=$(echo $ddir | tail -c 2)
if [ $lchar != "/" ] ; 
then
    ddir=$ddir/
fi


if [ -v $sdir ] ;
then
    echo "Error. Must provid a source directory using the -s parameter."
    exit 2
fi
    
#echo "Converting all files in directory" $sdir "and storing the result in " $ddir

for filename in $sdir/*; 
do

    filename_nodir=$(basename -- "$sdir/$filename")
    base="${filename_nodir%.*}"
    #ebook-convert "$sdir/$f"
    full_output_name=$ddir$base".epub"
    if [ $verbose == "True" ] ;
    then    
	echo "Converting" $filename to $full_output_name
    fi
    ebook-convert "$filename" "$full_output_name"
    
done
	   
	   

	  
