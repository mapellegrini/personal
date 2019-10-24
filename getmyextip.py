#!/usr/bin/python


import urllib

def getmyip():
  url="https://api.ipify.org"
  html = urllib.urlopen(url).read()
  return html


print getmyip()
