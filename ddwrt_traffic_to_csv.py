#!/usr/bin/python

from __future__ import print_function
import argparse

default_output = "/tmp/traffic.csv"
parser = argparse.ArgumentParser(description="Takes a DD-WRT traffic file "
                                 "and converts it to CSV of the format "
                                 "DATE,INCOMING(MB),OUTGOING(MB)")
parser.add_argument("-i", required=True,
                    help="The file to read in")
parser.add_argument("-o", required=False, default=default_output,
                    help="Output file path. Default:" + default_output)
args = parser.parse_args()

f = file(args.i, "r")
text = f.read().strip()
f.close()

lines = text.split("\n")
del lines[0] #remove first line, "TRAFF-DATA"
res = []

for line in lines:
    datestr,datastr = line.split("=")
    datestr=datestr[6:] #remove leading traff-
    data = datastr.split()
    for x in range(len(data)):
        if x >= 9:
            cdate = datestr[3:] + "-" + datestr[0:2] + "-" + str(x+1)
        else:
            cdate = datestr[3:] + "-" + datestr[0:2] + "-0" + str(x+1)

        if data[x] == "[0:0]":
            continue
        incoming, outgoing = data[x].split(":")
        #print(cdate + "," + incoming + "," + outgoing)
        res.append([cdate, incoming, outgoing])

res.sort()

#filter bad dates
month_lengths = {1:31, 2:28, 3:31, 4:30, 5:31, 6:30, 7:31, 8:31, 9:30,
                 10:31, 11:30, 12:31}
res2 = []
for entry in res:
    datestr = entry[0]
    year, month, day = datestr.split("-")
    if int(day) > month_lengths[int(month)]:
        if month == '2' and int(year) % 4 == 0:
            res2.append(entry)
        pass
    else:
        res2.append(entry)

#write to file
f = file(args.o, "w")
for entry in res2:
    f.write("%s,%s,%s\n" % (entry[0], entry[1], entry[2]))
f.close()
print("Wrote output to ", args.o)
