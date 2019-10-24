#!/bin/bash

while true;
do
  output=$(ping -q -c 10 8.8.8.8 | tail -n 2 | head -n 1)
  echo $(date) $output   
  sleep 300
done  
