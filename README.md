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

Copy `config.default.ini` to `config.ini` and add your devices:

```bash
cp config.default.ini config.ini
nano config.ini
```

```ini
[DEVICE_1]
MAC = xx:xx:xx:xx:xx:xx
KEY = your_32_character_hex_encryption_key
INSTANCE = 1

[DEVICE_2]
MAC = yy:yy:yy:yy:yy:yy
KEY = another_32_character_hex_key
INSTANCE = 2
```

**Note:** Device names are automatically read from the Bluetooth device itself.

### 3. Install on Cerbo GX

```bash
# Copy files to Cerbo GX
rsync -avz dbus-victron-orion-tr/ root@cerbo:/data/dbus-victron-orion-tr/

# SSH to Cerbo GX
ssh root@cerbo

# Make scripts executable
cd /data/dbus-victron-orion-tr
chmod +x start.sh stop.sh status.sh
```

**Note:** This service runs without supervision for easy manual control.

### 4. Start and Verify

```bash
# Start the service
./start.sh

# Check status
./status.sh

# View logs
tail -f /var/log/dbus-victron-orion-tr.log

# Check D-Bus (example for device with MAC ef:c1:11:9d:a3:91)
dbus -y com.victronenergy.dcdc.tr_2lfxwu69ht
```

## Service Management

```bash
# Start service
./start.sh

# Stop service
./stop.sh

# Check status
./status.sh

# View live logs
tail -f /var/log/dbus-victron-orion-tr.log
```

## Troubleshooting

### Service won't start

```bash
# Check logs
tail -100 /var/log/dbus-victron-orion-tr.log

# Check if BLE scanner is available
hciconfig hci0

# Test BLE scanning
bluetoothctl scan on
```

### No devices detected

1. Make sure Instant Readout is enabled in VictronConnect
2. Verify MAC addresses in config.ini match exactly
3. Check Bluetooth is working: `hciconfig hci0`
4. Try scanning manually: `bluetoothctl scan on`

### Wrong encryption key error

The encryption key changes when you change/reset the Bluetooth PIN. Get the current key from VictronConnect.

## How It Works

1. **BLE Scanning**: Continuously scans for Victron BLE advertisements
2. **Decryption**: Uses `victron_ble` library to decrypt Instant Readout data
3. **Mode Detection**: Automatically detects if device is in DC-DC or Charger mode
4. **D-Bus Publishing**: 
   - Power Supply mode → `com.victronenergy.dcdc.tr_<mac>`
   - Charger mode → `com.victronenergy.alternator.tr_<mac>`
5. **UI Integration**: Appears in Venus OS device list and VRM portal

```
Orion-TR (BLE) → BleakScanner → victron_ble → Mode Detection → D-Bus → Venus OS UI
                                      ↑
                              Encryption keys (config.ini)
```

## Dependencies

- **bleak**: BLE scanning
- **victron_ble**: Advertisement decryption and parsing  
- **velib_python**: Venus OS D-Bus integration

## Known Limitations

1. **No current/power data**: Orion-TR Smart devices do not measure or transmit current. Only voltages are available via BLE.
2. **Bluetooth range**: Devices must be within Bluetooth range of the Cerbo GX (typically 10-30 feet/3-10 meters).
3. **Encryption keys**: Must be obtained manually from VictronConnect for each device.
4. **No remote control**: The Orion-TR cannot be controlled remotely via BLE (no on/off switch in UI).
5. **BLE scanner conflicts**: May conflict with other BLE services on the Cerbo. Stop `dbus-ble-sensors` temporarily if needed.

## Development

### Project Structure

```
dbus-victron-orion-tr/
├── dbus-victron-orion-tr.py  # Main service
├── config.ini                # Device configuration (gitignored)
├── config.default.ini        # Configuration template
├── start.sh                  # Start service
├── stop.sh                   # Stop service
├── status.sh                 # Check service status
├── install.sh                # Installation script (optional)
└── ext/                      # Bundled dependencies
    ├── velib_python/         # Venus OS D-Bus library
    ├── victron_ble/          # Victron BLE protocol decoder
    ├── bleak/                # BLE scanning library
    └── Crypto/               # Cryptography library
```

### Key Features

- **Dynamic service type**: Automatically switches between `dcdc` and `alternator` based on device mode
- **Fallback product names**: Includes names for devices not in victron_ble database
- **Base36 MAC encoding**: Short, stable service names (e.g., `tr_2lfxwu69ht`)
- **Dynamic instance assignment**: Checks for existing settings and finds available instances
- **UI integration**: Appears in device list, VRM portal, and main overview

## References

- [Victron Orion-TR Smart Manual](https://www.victronenergy.com/dc-dc-converters/orion-tr-smart)
- [victron_ble Python Library](https://pypi.org/project/victron-ble/)
- [Venus OS Documentation](https://github.com/victronenergy/venus/wiki)

## License

This project is provided as-is for use with Victron Energy equipment.

## Credits

- Uses [victron_ble](https://github.com/keshavdv/victron-ble) by @keshavdv for BLE decryption
- Based on Victron's dbus-aggregate-smartshunts service architecture

