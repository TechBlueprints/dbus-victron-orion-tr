#!/bin/bash
#
# Enable script for dbus-victron-orion-tr
# This script is run on every boot via rc.local to ensure the service is properly set up
#

# Fix permissions
chmod +x /data/apps/dbus-victron-orion-tr/*.py
chmod +x /data/apps/dbus-victron-orion-tr/service/run
chmod +x /data/apps/dbus-victron-orion-tr/service/log/run

# Create rc.local if it doesn't exist
if [ ! -f /data/rc.local ]; then
    echo "#!/bin/bash" > /data/rc.local
    chmod 755 /data/rc.local
fi

# Add enable script to rc.local (runs on every boot)
RC_ENTRY="bash /data/apps/dbus-victron-orion-tr/enable.sh"
grep -qxF "$RC_ENTRY" /data/rc.local || echo "$RC_ENTRY" >> /data/rc.local

# Remove old-style symlink-only entries from rc.local
sed -i '/ln -sf \/data\/apps\/dbus-victron-orion-tr\/service \/service\/dbus-victron-orion-tr/d' /data/rc.local

# Create symlink to service directory
if [ -L /service/dbus-victron-orion-tr ]; then
    rm /service/dbus-victron-orion-tr
fi
ln -s /data/apps/dbus-victron-orion-tr/service /service/dbus-victron-orion-tr

echo "dbus-victron-orion-tr enabled"

