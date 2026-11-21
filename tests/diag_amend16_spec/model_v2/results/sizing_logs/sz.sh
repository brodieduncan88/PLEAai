#!/bin/sh
cd /tmp/claude-0/-home-user-PLEAai/62f931a2-70f8-57a8-80dd-4abcbc18f7e9/scratchpad/amend16/gate/model3; timeout 250 /usr/bin/python3.11 sizing.py "$1" '{}' 3000000 > results/sizing_logs/$1.txt 2>&1
