#!/bin/bash

display_usage() {
  echo "Usage: convertdir.sh [-h] -i <inputdir> -o <outputdir>"
  echo ""
  echo "Uses ffmpeg to convert a directory of avi/mpg/divx/wmv files to mp4 files"
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

#remove trailing slashes
targetdir=${targetdir%/}
sourcedir=${sourcedir%/}

#echo "Sourcedir = " $sourcedir
#echo "Targetdir = " $targetdir

for f in $sourcedir/*
do
    base=$(basename "${f%.*}")
    extension="${f##*.}"    
    if [[ $extension != "avi"  ]] &&
       [[ $extension != "divx" ]] &&
       [[ $extension != "wmv"  ]] &&
       [[ $extension != "mpg"  ]]; then
	continue
    fi
    #echo "base=" $base
    #echo "extension=" $extension
    
    target=$targetdir/$base    
    #replace spaces with underscores
    target=$(sed 's/ /_/g' <<< "$target")

    echo "Converting" $f "to" "$target.mp4"
    ffmpeg -i "$f" -c:v mpeg4 -c:a copy -y "$target.mp4"

    #alternative:
    #ffmpeg -i "$f" -strict -2 "$target/$name.mp4"    
done


for f in $sourcedir/*
do
    base=$(basename "${f%.*}")
    extension="${f##*.}"    
    if [[ $extension != "iso"  ]]; then
	continue
    fi
    
    dir=$(dirname "$f")
    target=$targetdir/$base

    #replace spaces with underscores
    target=$(sed 's/ /_/g' <<< "$target")
    name=$(sed 's/ /_/g' <<< "$name")

    echo "Converting" $f "to" "$target/$name.mp4"
    mkdir $target
    HandBrakeCLI -Z "High Profile" -i "$f" -o "$target/$name.mp4"
done


    
    
