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
exec 2>&1
cd /data/apps/dbus-victron-orion-tr
exec python3 -u dbus-victron-orion-tr.py
EOF

chmod +x "$INSTALL_DIR/service/run"

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

