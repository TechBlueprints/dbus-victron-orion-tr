# Dependencies

This project bundles external Python libraries in the `ext/` directory for deployment to Venus OS systems, which typically lack internet access and package management tools.

## Why Bundle Dependencies?

Venus OS (Cerbo GX, Venus GX, etc.) systems:
- **No pip or package manager** - cannot install from PyPI
- **Limited/no internet access** - especially in marine/RV environments
- **Immutable root filesystem** - custom software must be self-contained

This approach follows the pattern used by Victron's own [dbus-serialbattery](https://github.com/mr-manuel/venus-os_dbus-serialbattery) project.

## Bundled Libraries

### victron_ble (v0.8.0)
- **Purpose**: Victron BLE protocol decoder for instant readout data
- **Source**: https://github.com/keshavdv/victron-ble
- **License**: MIT
- **Why needed**: Decrypts and parses Victron Orion-TR BLE advertisement data
- **Note**: Only `victron_ble.devices` module is used; the `scanner` module is not needed as we use `dbus-ble-advertisements` router for BLE scanning

### pycryptodome (Crypto module)
- **Purpose**: Cryptographic operations for BLE advertisement decryption
- **Source**: https://github.com/Legrandin/pycryptodome
- **License**: BSD/Public Domain
- **Why needed**: Required by victron_ble for AES-CTR decryption of encrypted Victron BLE data

### velib_python
- **Purpose**: Venus OS D-Bus integration library
- **Source**: https://github.com/victronenergy/velib_python
- **License**: MIT
- **Why needed**: Publishes Orion-TR data to Venus OS D-Bus for GUI/VRM integration

## Architecture Note

This service uses the [dbus-ble-advertisements](https://github.com/techblueprints/dbus-ble-advertisements) router for BLE scanning. It does **not** directly interact with Bluetooth hardware - all BLE advertisements are received via D-Bus signals from the router service.

The Victron BLE protocol uses AES-CTR encryption with device-specific keys that must be retrieved from VictronConnect app.

## Updating Dependencies

### To update victron_ble:

1. Install the desired version locally:
   ```bash
   pip install victron-ble==0.8.0 --target=/tmp/deps
   ```

2. Copy to `ext/`:
   ```bash
   cp -r /tmp/deps/victron_ble ext/
   ```

3. Test on Venus OS to ensure compatibility

4. Update this file with the new version

### To update pycryptodome:

1. Install the desired version locally:
   ```bash
   pip install pycryptodome --target=/tmp/deps
   ```

2. Copy to `ext/`:
   ```bash
   cp -r /tmp/deps/Crypto ext/
   ```

3. Test on Venus OS to ensure compatibility

### To update velib_python:

1. Clone the latest version:
   ```bash
   git clone https://github.com/victronenergy/velib_python /tmp/velib_python
   ```

2. Copy to `ext/`:
   ```bash
   cp -r /tmp/velib_python ext/
   ```

3. Test on Venus OS to ensure compatibility

## For Developers

When developing locally, you can install dependencies normally:

```bash
pip install victron-ble pycryptodome
```

The code will preferentially import from `ext/` when running on Venus OS, falling back to system packages for local development.

