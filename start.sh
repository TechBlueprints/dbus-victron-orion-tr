#!/bin/bash
# Start the Orion-TR service manually

cd /data/apps/dbus-victron-orion-tr

# Check if already running
if pgrep -f dbus-victron-orion-tr.py > /dev/null; then
    echo 'Service is already running!'
    exit 1
fi

# Start in background and log to file
echo 'Starting Orion-TR service...'
python3 dbus-victron-orion-tr.py > /var/log/dbus-victron-orion-tr.log 2>&1 &
sleep 2

# Check if started
if pgrep -f dbus-victron-orion-tr.py > /dev/null; then
    echo 'Service started successfully!'
    echo 'View logs: tail -f /var/log/dbus-victron-orion-tr.log'
else
    echo 'Failed to start service. Check /var/log/dbus-victron-orion-tr.log'
    exit 1
fi
