#!/bin/bash
# Stop the Orion-TR service

echo 'Stopping Orion-TR service...'
pkill -f dbus-victron-orion-tr.py

sleep 1

# Verify stopped
if pgrep -f dbus-victron-orion-tr.py > /dev/null; then
    echo 'Failed to stop service!'
    exit 1
else
    echo 'Service stopped successfully!'
fi
