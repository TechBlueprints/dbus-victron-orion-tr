#!/bin/bash
#
# Installation script for dbus-victron-orion-tr on Venus OS (Cerbo GX)
#
# This script installs the service to /data/apps/dbus-victron-orion-tr
# and sets it up to run automatically via daemontools (supervise/svc)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="/data/apps/dbus-victron-orion-tr"

echo "=========================================="
echo "Installing dbus-victron-orion-tr"
echo "=========================================="
echo ""

# Check if running on Venus OS
if [ ! -d "/data/apps" ]; then
    echo "Error: /data/apps not found. This script must run on Venus OS."
    exit 1
fi

# Check if dbus-ble-advertisements is installed
echo "Checking for dbus-ble-advertisements service..."
if ! dbus-send --system --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus.ListNames 2>/dev/null | grep -q "com.victronenergy.ble.advertisements"; then
    echo ""
    echo "=========================================="
    echo "dbus-ble-advertisements NOT FOUND"
    echo "=========================================="
    echo ""
    echo "This service requires the dbus-ble-advertisements router."
    echo ""
    
    # Check if we can auto-install
    if command -v curl >/dev/null 2>&1; then
        echo "Would you like to install it now? (y/n)"
        read -r response
        if [ "$response" = "y" ] || [ "$response" = "Y" ]; then
            echo ""
            echo "Installing dbus-ble-advertisements..."
            curl -fsSL https://raw.githubusercontent.com/TechBlueprints/dbus-ble-advertisements/main/install.sh | bash
            if [ $? -eq 0 ]; then
                echo ""
                echo "✓ dbus-ble-advertisements installed successfully"
                echo ""
            else
                echo ""
                echo "ERROR: Failed to install dbus-ble-advertisements"
                echo "Please install manually from: https://github.com/TechBlueprints/dbus-ble-advertisements"
                exit 1
            fi
        else
            echo ""
            echo "Installation cancelled. You must install dbus-ble-advertisements first:"
            echo "  curl -fsSL https://raw.githubusercontent.com/TechBlueprints/dbus-ble-advertisements/main/install.sh | bash"
            echo ""
            echo "Or use the legacy-standalone-bleak branch:"
            echo "  https://github.com/TechBlueprints/dbus-victron-orion-tr/tree/legacy-standalone-bleak"
            exit 1
        fi
    else
        echo "Manual installation required:"
        echo "  wget -qO- https://raw.githubusercontent.com/TechBlueprints/dbus-ble-advertisements/main/install.sh | bash"
        echo ""
        echo "Or use the legacy-standalone-bleak branch:"
        echo "  https://github.com/TechBlueprints/dbus-victron-orion-tr/tree/legacy-standalone-bleak"
        exit 1
    fi
fi

echo "✓ dbus-ble-advertisements service found"
echo ""

# Create installation directory
echo "Creating installation directory..."
mkdir -p "$INSTALL_DIR"

# Copy files
echo "Copying files..."
cp "$SCRIPT_DIR/dbus-victron-orion-tr.py" "$INSTALL_DIR/"
cp "$SCRIPT_DIR/config.ini" "$INSTALL_DIR/"
cp -r "$SCRIPT_DIR/ext" "$INSTALL_DIR/"

# Make main script executable
chmod +x "$INSTALL_DIR/dbus-victron-orion-tr.py"

# Create service directory for daemontools
echo "Setting up service..."
mkdir -p "$INSTALL_DIR/service"

# Create run script
cat > "$INSTALL_DIR/service/run" << 'EOF'
#!/bin/sh
echo "*** starting dbus-victron-orion-tr ***"
exec 2>&1
. /etc/profile.d/profile.sh

# Wait for dbus-ble-advertisements service with retry logic
MAX_RETRIES=30
RETRY_DELAY=2
RETRY_COUNT=0

echo "Waiting for dbus-ble-advertisements service..."

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    # Check for advertisement emitter service
    if dbus-send --system --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus.ListNames 2>/dev/null | grep -q "com.victronenergy.ble.advertisements"; then
        echo "✓ Router service found after $RETRY_COUNT attempts"
        break
    fi
    
    RETRY_COUNT=$((RETRY_COUNT + 1))
    
    if [ $RETRY_COUNT -eq 1 ]; then
        echo "Waiting for dbus-ble-advertisements service to start..."
    elif [ $RETRY_COUNT -eq 15 ]; then
        echo "Still waiting... (${RETRY_COUNT}/${MAX_RETRIES} attempts)"
    fi
    
    sleep $RETRY_DELAY
done

# Final check
if ! dbus-send --system --print-reply --dest=org.freedesktop.DBus /org/freedesktop/DBus org.freedesktop.DBus.ListNames 2>/dev/null | grep -q "com.victronenergy.ble.advertisements"; then
    echo ""
    echo "=========================================="
    echo "ERROR: dbus-ble-advertisements not found!"
    echo "=========================================="
    echo ""
    echo "This service requires the dbus-ble-advertisements router."
    echo ""
    echo "Please install it from:"
    echo "  https://github.com/TechBlueprints/dbus-ble-advertisements"
    echo ""
    echo "Alternative: Use the legacy-standalone-bleak branch:"
    echo "  https://github.com/TechBlueprints/dbus-victron-orion-tr/tree/legacy-standalone-bleak"
    echo ""
    sleep 10  # Brief pause before supervisor restarts
    exit 1
fi

echo "Starting orion-tr service..."
cd /data/apps/dbus-victron-orion-tr
exec python3 -u dbus-victron-orion-tr.py
EOF

chmod +x "$INSTALL_DIR/service/run"

# Add to rc.local to persist across reboots
RC_LOCAL="/data/rc.local"
RC_ENTRY="bash $INSTALL_DIR/install-reboot.sh > $INSTALL_DIR/startup.log 2>&1 &"
SERVICE_LINK="/service/dbus-victron-orion-tr"

if [ ! -f "$RC_LOCAL" ]; then
    echo "Creating /data/rc.local..."
    echo "#!/bin/bash" > "$RC_LOCAL"
    chmod 755 "$RC_LOCAL"
fi

# Create a simple reboot script that just recreates the symlink
cat > "$INSTALL_DIR/install-reboot.sh" << 'REBOOT_SCRIPT'
#!/bin/bash
# Recreate service symlink on reboot
INSTALL_DIR="/data/apps/dbus-victron-orion-tr"
SERVICE_LINK="/service/dbus-victron-orion-tr"

if [ ! -L "$SERVICE_LINK" ]; then
    ln -s "$INSTALL_DIR/service" "$SERVICE_LINK"
fi
REBOOT_SCRIPT

chmod +x "$INSTALL_DIR/install-reboot.sh"

if ! grep -qF "$RC_ENTRY" "$RC_LOCAL"; then
    echo "Adding service to rc.local for persistence across reboots..."
    echo "$RC_ENTRY" >> "$RC_LOCAL"
    echo "✓ Added to rc.local"
else
    echo "✓ Already in rc.local"
fi

# Link to daemontools service directory
echo "Registering service with daemontools..."
if [ -L "/service/dbus-victron-orion-tr" ]; then
    echo "Service link already exists, removing..."
    svc -d /service/dbus-victron-orion-tr
    rm /service/dbus-victron-orion-tr
fi

ln -s "$INSTALL_DIR/service" /service/dbus-victron-orion-tr

echo ""
echo "=========================================="
echo "Installation complete!"
echo "=========================================="
echo ""
echo "The service will start automatically in a few seconds."
echo ""
echo "Service management commands:"
echo "  svc -u /service/dbus-victron-orion-tr  # Start service"
echo "  svc -d /service/dbus-victron-orion-tr  # Stop service"
echo "  svc -t /service/dbus-victron-orion-tr  # Restart service"
echo "  svstat /service/dbus-victron-orion-tr  # Check status"
echo ""
echo "View logs:"
echo "  tail -f /data/apps/dbus-victron-orion-tr/service/log/current"
echo ""

