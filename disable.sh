#!/bin/bash
#
# Disable script for dbus-victron-orion-tr
# Cleanly stops and removes the service and all its settings
#

# remove comment for easier troubleshooting
#set -x

INSTALL_DIR="/data/apps/dbus-victron-orion-tr"
SERVICE_NAME="dbus-victron-orion-tr"

echo
echo "Disabling $SERVICE_NAME..."

# Remove service symlink
rm -rf "/service/$SERVICE_NAME" 2>/dev/null || true

# Kill any remaining processes
pkill -f "supervise $SERVICE_NAME" 2>/dev/null || true
pkill -f "multilog .* /var/log/$SERVICE_NAME" 2>/dev/null || true
pkill -f "python.*$SERVICE_NAME" 2>/dev/null || true
pkill -f "python.*orion" 2>/dev/null || true

# Remove enable script from rc.local
sed -i "/.*$SERVICE_NAME.*/d" /data/rc.local 2>/dev/null || true

echo "Service stopped and rc.local cleaned"

# Clean up D-Bus settings
echo "Cleaning up D-Bus settings..."

# Function to delete a settings path
delete_setting() {
    local path="$1"
    dbus -y com.victronenergy.settings "$path" SetValue "" 2>/dev/null || true
}

# Clean up settings paths for orion-tr devices
for path in $(dbus -y com.victronenergy.settings / GetValue 2>/dev/null | grep -oE "Settings/Devices/orion_tr/[^']*" | sort -u); do
    echo "  Removing /$path"
    delete_setting "/$path"
done

# Clean up dcdc device settings (device instance settings)
for path in $(dbus -y com.victronenergy.settings / GetValue 2>/dev/null | grep -oE "Settings/Devices/dcdc[^']*" | sort -u); do
    echo "  Removing /$path"
    delete_setting "/$path"
done

echo
echo "$SERVICE_NAME disabled and settings cleaned"
echo
echo "Note: To completely remove, also delete: $INSTALL_DIR"
echo
