#!/bin/bash
set -m

cd /app
python server.py &

# start an agent in the Caldera container
cd /app/plugins/sandcat/payloads
./sandcat &

fg %1
