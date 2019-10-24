#!/usr/bin/python

import sys
import os
import subprocess
import hashlib
import argparse
import pickle

def getstdout(command):
  proc = subprocess.Popen(command, stdout=subprocess.PIPE)
  output = proc.stdout.read()
  return output.lstrip().rstrip()


def getmd5(file):
  return getstdout(['md5sum',file])[0:32]


def get_file_hash(path):
    f = file(path, "rb")
    h = hashlib.sha256()
    data = f.read(h.block_size)
    while data:
        h.update(data)
        data = f.read(1024)
    f.close()
    return h.digest()

def check_dupes (file_list):
#takes a list of files with length >= 2 
#returns true if they all hard link to the same inode
#returns false otherwise 
  inode = os.stat(file_list[0]).st_ino
  for a in range (1, len(file_list)):
    #print inode
    #print os.stat(mydict[ent][a]).st_ino
    if (inode != os.stat(file_list[a]).st_ino):
      return False
  return True 


parser = argparse.ArgumentParser(description="Find duplicate files and delete or link them.")
parser.add_argument("-p", dest="preprint", required=False, action="store_true", help="Print all matches prior first.")
parser.add_argument("-n", dest="name",     required=False, action="store_true", help="Compare files based only on the filenames (case sensitive).")
parser.add_argument("-s", default=True,    required=False, action="store_true", help="Ignore symlinks.")
parser.add_argument("-i",                  required=False, default="",          help="Input pickled hashes from specified output file.")
parser.add_argument("-o",                  required=False, default="",          help="Output pickled hashes to specified output file.")
parser.add_argument('--autodel', type=str, required=False, action='append', default=[])
parser.add_argument("directory", type=str, help="The directory to be processed")
args = parser.parse_args()


if (args.i != ""):
  f = file(args.i, "r")
  mydict = pickle.load(f)
  f.close()
else:
  mydict = {}

for a in range(0, len(args.autodel)):
  if (args.autodel[a].startswith("./")):
    wd = os.getcwd()
    args.autodel[a] = wd + "/" + args.autodel[a][2:]
  if (os.path.isdir(args.autodel[a])==False):
    print "ERROR - automatically deletable directory is not a directory or does not exist:", args.autodel[a] 
    sys.exit(1)  


cnt = 0 
for root, dirs, files in os.walk(args.directory):
  for f in files:
    cnt = cnt + 1 

total = cnt
cnt = 0 

for root, dirs, files in os.walk(args.directory):
  for f in files:
    cnt += 1
    if (cnt % 500 == 0):
      print "Now hashing file #", cnt, " out of ", total, "(", round(100*float(cnt)/total, 2), "%)"
    if (root.endswith("/")):
      filename = root + f
    else:
      filename = root + "/" + f 

    #symlink handling
    if (os.path.islink(filename)):
      if (args.s == True):
        continue 
      if (os.path.exists(filename)): 
        print "Error - symlink " + filename + " links to non-existant location. Ignoring it"
        continue
              
    if (args.name):
      myhash = f
    else:
      myhash = get_file_hash(filename)
            
    if (mydict.has_key(myhash)):
      mydict[myhash].append(filename)
    else:
      mydict[myhash] = [filename]

if (args.o != ""):
  f = file(args.o, "w")
  pickle.dump(mydict, f)
  f.close()


if (args.preprint):
  colcnt = 0
  for ent in mydict:
    if (len(mydict[ent]) > 1) and check_dupes(mydict[ent]) == False:
      colcnt += 1 
      print "Preprinting collision:"        
      for a in range (0, len(mydict[ent])):
        print a, mydict[ent][a]
      print "\n"
  print colcnt, "collisions found" 


colcnt = 0 
for ent in mydict:
  if (len(mydict[ent]) > 1):
    colcnt += 1 
    uinput = "0"
      
    #scan for autodel items 
    while ((uinput != -1) and len(mydict[ent])>1) and check_dupes(mydict[ent]) == False:
      for a in range (len(mydict[ent])-1, -1, -1):
        if (len(mydict[ent]) == 1):
          break 
        changed = False
        for autodir in args.autodel:
          if (os.path.isabs(mydict[ent][a])):
            base = ""
          else:
            base = os.getcwd() + "/"
          #print a, base+mydict[ent][a], autodir
          if ((base+mydict[ent][a]).startswith(autodir)):
            print "Deleting autodel dupe", base+mydict[ent][a]
            changed=True
            os.unlink(base+mydict[ent][a])
            del mydict[ent][a]
            break  
      if(changed==True):
        continue 
      #print "exiting"
      #sys.exit(5)


      print "Collision #" + str(colcnt) + " - which one(s) do you want to delete?"        
      for a in range (0, len(mydict[ent])):
          print a, mydict[ent][a]
      print "Enter l to (hard) link them" 
      print "Enter key to keep all" 

      entry = raw_input("Enter your choice -> ")

      if (entry == "l"):                  
        for a in range (1, len(mydict[ent])):
          if (os.path.isabs(mydict[ent][0])):
            base = ""
          else:
            base = os.getcwd() + "/"
          os.unlink(mydict[ent][a])
          os.link(base + mydict[ent][0], mydict[ent][a])

      if (entry == "l" or entry == "" or entry == "-1"):
        print "\n"
        break

      try:
        uinput = int(entry)
      except ValueError:
        print "Oops!  That was no valid number.  Try again..."
        continue

      if (uinput >=0):
        if (uinput < len(mydict[ent])):
          os.unlink(mydict[ent][uinput])
          del mydict[ent][uinput]
        else:
          print "ERROR - invalid number"
      elif (uinput != -1):
          print "ERROR - invalid number"
 
