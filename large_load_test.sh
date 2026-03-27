#!/bin/bash
# Runs a large number of load tests on the server and saves stderr to err.txt and other logs to res.txt

ITER=${1:-20}
echo "Starting $ITER load tests on dhcp server"

for ((i = 0; i < ITER; i++)); do
    echo "Iteration $i"
    /home/bennett/workspace/dhcp-ipam/.venv/bin/python3 openIPAM/dhcp_load_test.py >> res.txt 2>> err.txt
done

echo "Finished load test! View errors in err.txt and logs in res.txt"