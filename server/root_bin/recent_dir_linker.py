#!/usr/bin/python3

import argparse
import os
import collections
import shutil
#from datetime import datetime, timedelta
import datetime

parser = argparse.ArgumentParser(description='Prints either the N newest '
                                 'files (new mode), or those created in the '
                                 'last N days (recent mode)')
parser.add_argument('-m', required=True, choices=['new', 'recent'],
                    help='Run in new/recent mode')
parser.add_argument('-n', required=True, type=int,
                    help='Number of directories to print')
parser.add_argument('-d', required=True, nargs='+',
                    help='Directories to parse')
parser.add_argument('-s', required=False, default='',
                    help='Create links in this directory')
parser.add_argument('-l', required=False, action='store_true', default=False,
                    help='Create hard links rather than symlinks')

args = parser.parse_args()

dateformat='%Y_%m_%d_%H_%M_%S'


def getsubdirs(d):
    if not d.endswith("/"):
        d += "/"    
    res = []
    dirs = os.listdir(d) 
    for subdir in dirs:
        if os.path.isdir(d + subdir):
            res.append(d+subdir)
    return res


def get_date_dir_map(dirs):
    date_to_file_map = {}
    for cdir in dirs:
        unix_time = os.stat(cdir).st_mtime
        date = datetime.datetime.fromtimestamp(unix_time, datetime.UTC)
        #date = datetime.utcfromtimestamp(unix_time)
        datestr = date.strftime(dateformat)
        while datestr in date_to_file_map:
            date =  date + datetime.timedelta(seconds=1)
            datestr = date.strftime(dateformat)
        date_to_file_map[datestr] = cdir
    sorted_dates = sorted(date_to_file_map, reverse=True)
    res = collections.OrderedDict()
    for date in sorted_dates:
        res[date]=date_to_file_map[date]
    return res


def get_changed_dirs(d):
    res = []
    subdirs = getsubdirs(d)
    date_dir_map = get_date_dir_map(subdirs)
    date_dir_list =  list(date_dir_map.items())
    
    if args.m == "new":
        for date,cdir in list(date_dir_map.items())[0:args.n]:            
            res.append(cdir)
    if args.m == "recent":
        days_ago = datetime.datetime.now() - datetime.timedelta(days=args.n)
        days_ago_str = days_ago.strftime(dateformat)
        for date,cdir in date_dir_map.items():
            if days_ago_str > date:
                break
            res.append(cdir)
    return res
    
    
for d in args.d:
    changed_dirs = get_changed_dirs(d)
    if args.s:
        if not args.s.endswith("/"):
            args.s += "/"
        for d in changed_dirs:
            filename = os.path.basename(d)
            sourcename = args.s + filename

            if args.l:
                print("Creating hardlink:", d, "<---", sourcename)
                shutil.copytree(d, sourcename, copy_function=os.link)
                
            else:
                print("Creating symlink:", d, "<---", sourcename)
                os.symlink(d, sourcename)


