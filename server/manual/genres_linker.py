#!/usr/bin/python3

import os
import json
import datetime
from shutil import copyfile, rmtree

sourcedir = '/mnt/data2/movie/'
targetdir = '/mnt/data2/genres'
json_path = '/mnt/data/software/video_genres/genres.json'


def get_dir_list(rootDir):
    res = []
    for dirName, subdirList, fileList in sorted(os.walk(rootDir)):
        if dirName[len(sourcedir):].find('/') == -1:
            continue
        res.append(dirName)
    return res

def load_json(path):
    try:
        with open(path, "r") as fh:
            text = fh.read()
    except IOError: # file is missing / unreadable
        return {}
    return json.loads(text)

def write_json(json_path, genre_dict):
    if os.path.exists(json_path):
        json_dir, json_filename = os.path.split(json_path)
        backup_filename = json_filename + "." + \
            str(datetime.datetime.utcnow()).replace(" ", "_")
        backup_path = os.path.join(json_dir, backup_filename)
        copyfile(json_path, backup_path)
    
    text = json.dumps(genre_dict, sort_keys=True)
    with open(json_path, "w") as fh:
        json.dump(genre_dict, fh, indent=4, sort_keys=True)
    return


def create_links(targetdir, dir_genre_map):
    if os.path.exists(targetdir):
        for tfile in os.scandir(targetdir):
            rmtree(tfile.path)
    else:
        os.mkdir(targetdir)
    
    for sdir, genres in dir_genre_map.items():
        for genre in genres:
            genre = genre.lower()
            movie_name = sdir[sdir.rfind('/')+1:]
            tpath = os.path.join(targetdir, genre)
            dest_dir = os.path.join(tpath, movie_name)

            if not os.path.exists(tpath):
                os.mkdir(tpath)
            os.mkdir(dest_dir)
            for movie_file in os.listdir(sdir):
                src_path = os.path.join(sdir, movie_file)
                dest_path = os.path.join(dest_dir, movie_file)
                os.link(src_path, dest_path)
                #print("link {} -> {}".format(str(movie_file), tpath)) 

dir_genre_map = load_json(json_path)
directories = get_dir_list(sourcedir)
for directory in directories:
    if directory in dir_genre_map:
        continue
    dir_genre_map[directory] = []
create_links(targetdir, dir_genre_map)
write_json(json_path, dir_genre_map)
