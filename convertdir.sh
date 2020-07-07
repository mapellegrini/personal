#!/bin/bash

display_usage() {
  echo "Usage: convertdir.sh [-h] -i <inputdir> -i <outputdir>"
  echo ""
  echo "Uses ffmpeg to convert a directory of avi files to mp4 files"
}

randomstr="ljljlksdjljwljleii3kd"
sourcedir=$randomstr
targetdir=$randomstr


while getopts "hi:o:" opt; do #variables that take an argument are followed by a colon 
  case ${opt} in
    h | \? | help )
      display_usage; 
      exit 0 
      ;;
    i )
      sourcedir=$OPTARG
      ;;
    o )
      targetdir=$OPTARG
    esac
done


if [ $sourcedir == $randomstr ]; then
    echo "An input directory (-i) is required"
    exit 1 
fi


if [ $targetdir == $randomstr ]; then
    echo "An output directory (-o) is required"
    exit 2
fi


for f in $sourcedir/*/*.avi
do
    name=$(basename "$f" ".avi")
    dir=$(dirname "$f")
    base=$(basename $dir)
    target=$targetdir/$base
    
    #replace spaces with underscores
    target=$(sed 's/ /_/g' <<< "$target")
    name=$(sed 's/ /_/g' <<< "$name")

    echo "Converting" $f "to" "$target/$name.mp4"
    mkdir $target
    ffmpeg -i "$f" -c:v copy -c:a copy -y "$target/$name.mp4"
done
	    
