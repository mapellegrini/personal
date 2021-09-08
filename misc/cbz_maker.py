#!/usr/bin/python3

import os
import sys
from shutil import copyfile

def print_usage():
    my_name = sys.argv[0]
    print('Usage: {my_name} [-h] [source_dir] [target_dir]') 
    print('source_dir: The path to a directory-of-directories. Default: .')
    print('target_dir: The path to write files to. Default: source_dir/cbz')


if len(sys.argv) > 1:
    if sys.argv[1] in ('-h', '--h', '--help'):
        print_usage()
        sys.exit(0)
    source_dir = sys.argv[1]
else:
    source_dir = "."

if len(sys.argv) > 2:
    target_dir = sys.argv[2]
else:
    target_dir = os.path.join(source_dir, "cbz")

file_dir_map = {}
for root, dirs, files in os.walk(source_dir, topdown=True):
    if root == source_dir:
        continue
    for f in files:
        _, extension = os.path.splitext(f)
        if extension not in ('.png', '.jpg', '.gif', '.jpeg'):
            continue
        path = os.path.join(root, f)
        basename = os.path.basename(path)
        dirname = os.path.basename(os.path.dirname(path))
        file_dir_map[path] = (dirname, basename)

os.mkdir(target_dir)
for source_path, (dirname, basename) in file_dir_map.items():
    dirname = dirname.replace(' ', '_')
    target_name = dirname + '_' + basename.replace(" ", "_")
    target_path = os.path.join(target_dir, target_name)

    print(source_path, '-->', target_path)
    try:
        copyfile(source_path, target_path)
    except Exception as err:
        print('Exception: {} \noccured while copying {} to {}'.format(
            err, source_path, target_path))
    

