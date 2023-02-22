#!/usr/bin/python3

import argparse
import os
import sys
import subprocess
import shutil

ALLOWED_FILES = ['.avi', '.mp4', '.mkv']
CONVERTABLE_FORMATS = ['dts', 'e-ac-3']

def getstdout(command):
    #print("Command = ", command)
    proc = subprocess.Popen(command, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, shell=True)
    #output = proc.stdout.read()
    output = proc.stdout.read().decode()
    return output.lstrip().rstrip()


def get_audio_format(path):
    output = getstdout(f'mediainfo "{path}"')
    #print("\npath=", path, "\noutput = ", output)
    audiopos = output.find("\nAudio")
    formatpos = output.find("Format", audiopos)
    formatpos_end = output.find("\n", formatpos)
    format_str = output[formatpos:formatpos_end].split()[-1]
    return format_str.lower()


def get_files(source_dir, debug):
    file_dir_map = {}
    for root, dirs, files in os.walk(source_dir, topdown=True):
        #print("root = ",root)
        #print("source_dir = ",source_dir)
        #print("dirs = ", dirs)
        #print("files = ", files)
        if root == source_dir:
            continue
        for f in files:
            _, extension = os.path.splitext(f)
            if extension not in ALLOWED_FILES:
                if debug:
                    print("!! found nonmatching file: ", f)
                continue
            path = os.path.join(root, f)
            basename = os.path.basename(path)
            dirname = os.path.basename(os.path.dirname(path))
            file_dir_map[path] = (dirname, basename)

    return file_dir_map

############################################

parser = argparse.ArgumentParser(
  description='Convert a directory of video files to use aac audio codec',
  formatter_class=argparse.ArgumentDefaultsHelpFormatter
)
parser.add_argument('-d', '--directory', required=True,
                    help="The input directory")
parser.add_argument('--debug', action='store_true', required=False,
                     default=False)
args = parser.parse_args()


file_dir_map = get_files(args.directory, args.debug)
for path, (topdir, filename) in file_dir_map.items():
    extension = os.path.splitext(path)[1]
    #print(path, "--", topdir, "--", filename)
    audio_format = get_audio_format(path)
    print(f"{path} -> {audio_format}")
    if audio_format in CONVERTABLE_FORMATS:
        print("Will convert file")
        new_path = f'{path}.new{extension}'  # a.mkv -> a.mkv.new.mkv
        old_path = f'{path}.old'
        command = f'ffmpeg -analyzeduration 100M -probesize 100M -i "{path}" -acodec aac -vcodec copy "{new_path}"'
        result = getstdout(command)
        #print("result = ", result)
        shutil.move(path, old_path)
        shutil.move(new_path, path)
    else:
        print("Will skip file")
