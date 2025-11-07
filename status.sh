#!/bin/bash
# Check status of Orion-TR service

if pgrep -f dbus-victron-orion-tr.py > /dev/null; then
    echo '✓ Service is running'
    echo ''
    echo 'Processes:'
    ps aux | grep dbus-victron-orion-tr.py | grep -v grep
    echo ''
    echo 'D-Bus services:'
    dbus -y | grep 'alternator.tr_' || echo '  (none found yet)'
else
    echo '✗ Service is not running'
fi
