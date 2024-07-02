#!/usr/bin/python3

import argparse
import os
import shutil
from pathlib import Path


def parsedir(directory, args, level):
    """
    Directory: The path to the target directory
    level: The recursion level
    """
    if level == 0 or not os.path.isdir(directory):
        return

    for f in os.listdir(directory):
        old_full_path = os.path.join(directory, f)

        if not os.path.isdir(old_full_path):
            return        
        if os.path.isdir(old_full_path):
            parsedir(old_full_path, args, level-1)
        if f.lower().startswith(article + ' ') or \
           f.lower().startswith(article + '_'):
            new_name = f[len(article)+1:] + '_' + article.title()
            first_letter = new_name[0]
            if first_letter.isdecimal():
                first_letter = '0-9'
            else:
                first_letter = first_letter.upper()
            new_full_path = os.path.join(
                parent_dir, first_letter, new_name)
            if args.print:
                print(f'Would move {old_full_path} to {new_full_path}')
            else:
                print(f'Moving {old_full_path} to {new_full_path}')
                shutil.move(old_full_path, new_full_path,
                            copy_function=shutil.copytree)


parser = argparse.ArgumentParser(
  description='Renames and moves files starting with articles',
  formatter_class=argparse.ArgumentDefaultsHelpFormatter
)
parser.add_argument('-d', '--directories', required=True,
                    help="A comma-seperated list of directories")
parser.add_argument('-p', '--print', action='store_true', default=False,
                    help='Print only. Do not move files')
parser.add_argument('-r', '--recursion', type=int, default=2,
                    help='Recursion level')
args = parser.parse_args()

articles = ('a', 'an', 'the')  # must all be lower case
decimals = ('0', '1', '2', '3', '4', '5', '6', '7', '8', '9')
directories = args.directories.split(',')


for article in articles:
    for directory in directories:
        parent_dir = Path(directory).parent.absolute()
        path = os.path.join(parent_dir, directory)
        parsedir(path, args, args.recursion)

