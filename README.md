# dbus-victron-orion-tr

Venus OS D-Bus service for Victron Orion-TR Smart DC-DC Converters via Bluetooth LE.

This service scans for Victron Orion-TR Smart devices via Bluetooth, decrypts their Instant Readout advertisements, and publishes voltage and status information to D-Bus so they appear in the Venus OS dashboard.

## Features

- ✅ Automatic BLE scanning and device discovery
- ✅ Encrypted Instant Readout decryption
- ✅ Real-time monitoring of:
  - Input voltage
  - Output voltage  
  - Operating state (Power Supply, Off, etc.)
  - Error conditions
- ✅ Multiple device support
- ✅ Venus OS D-Bus integration

## Supported Devices

- Victron Orion-TR Smart (all models)
  - Isolated and non-isolated versions
  - All voltage/current ratings

**Note:** The Orion-TR Smart devices do NOT measure or report current/power. Only voltages and operating state are available.

## Requirements

- Venus OS (Cerbo GX, Venus GX, etc.)
- Victron Orion-TR Smart with Bluetooth
- VictronConnect app (to get encryption keys)

## Installation

### 1. Get Encryption Keys

For each Orion-TR device you want to monitor:

1. Open **VictronConnect** app on your phone
2. Connect to the device
3. Tap the **gear icon** (Settings)
4. Tap **three dots** (top right) → **Product Info**
5. Scroll to **"Instant Readout via Bluetooth"**
6. Make sure it's **ENABLED**
7. Tap **"SHOW"** next to "Instant readout details"
8. Note down the **MAC Address** and **Encryption Key**

### 2. Configure

Edit `config.ini` and add your devices:

```ini
# Device 1
DEVICE_1_MAC="xx:xx:xx:xx:xx:xx"
DEVICE_1_NAME="My Orion-TR"
DEVICE_1_KEY="your_encryption_key_here"
DEVICE_1_INSTANCE=1
```

### 3. Install on Cerbo GX

```bash
# Copy files to Cerbo GX
scp -r dbus-victron-orion-tr root@cerbo:/data/tmp/

# SSH to Cerbo GX
ssh root@cerbo

# Run installation script
cd /data/tmp/dbus-victron-orion-tr
chmod +x install.sh
./install.sh
```

### 4. Verify

```bash
# Check service status
svstat /service/dbus-victron-orion-tr

# View logs
tail -f /data/apps/dbus-victron-orion-tr/service/log/current

# Check D-Bus (once implemented)
dbus -y com.victronenergy.dcdc.orion_tr_1
```

## Service Management

```bash
# Start service
svc -u /service/dbus-victron-orion-tr

# Stop service
svc -d /service/dbus-victron-orion-tr

# Restart service
svc -t /service/dbus-victron-orion-tr

# Check status
svstat /service/dbus-victron-orion-tr
```

## Troubleshooting

### Service won't start

```bash
# Check logs
tail -100 /data/apps/dbus-victron-orion-tr/service/log/current

# Check if Python dependencies are available
python3 -c "import victron_ble; print('OK')"
```

### No devices detected

1. Make sure Instant Readout is enabled in VictronConnect
2. Verify MAC addresses in config.ini match exactly
3. Check Bluetooth is working: `hciconfig hci0`
4. Try scanning manually: `bluetoothctl scan on`

### Wrong encryption key error

The encryption key changes when you change/reset the Bluetooth PIN. Get the current key from VictronConnect.

## Architecture

```
Orion-TR (BLE) → BleakScanner → victron_ble decoder → D-Bus → Venus OS
                                      ↑
                              Encryption keys
```

## Dependencies

- **bleak**: BLE scanning
- **victron_ble**: Advertisement decryption and parsing  
- **velib_python**: Venus OS D-Bus integration

## Known Limitations

1. **No current/power data**: Orion-TR Smart devices do not measure or transmit current. Only voltages are available.
2. **Bluetooth range**: Devices must be within Bluetooth range of the Cerbo GX (typically 10-30 feet/3-10 meters).
3. **Encryption keys**: Must be obtained manually from VictronConnect for each device.

## Development

### Project Structure

```
dbus-victron-orion-tr/
├── dbus-victron-orion-tr.py  # Main service
├── config.ini                # Device configuration
├── install.sh                # Installation script
├── service/
│   └── run                   # Daemontools run script
└── ext/
    ├── velib_python/         # Venus OS D-Bus library
    └── bleak/                # BLE library (if not system-installed)
```

### Testing Locally

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install victron_ble bleak

# Run service (with Bluetooth enabled)
python dbus-victron-orion-tr.py
```

## References

- [Victron Orion-TR Smart Manual](https://www.victronenergy.com/dc-dc-converters/orion-tr-smart)
- [victron_ble Python Library](https://pypi.org/project/victron-ble/)
- [Venus OS Documentation](https://github.com/victronenergy/venus/wiki)

## License

This project is provided as-is for use with Victron Energy equipment.

## Credits

- Uses [victron_ble](https://github.com/keshavdv/victron-ble) by @keshavdv for BLE decryption
- Based on Victron's dbus-aggregate-smartshunts service architecture

