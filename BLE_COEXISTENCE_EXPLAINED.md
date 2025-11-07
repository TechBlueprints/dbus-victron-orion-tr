# How Multiple BLE Scanners Coexist

## The Mystery
Both `dbus-ble-sensors` and `dbus-victron-orion-tr` can scan for BLE advertisements **simultaneously** without conflicts, even though we initially got "Operation already in progress" errors.

## The Answer: Different Scanning Layers

### 1. dbus-ble-sensors (C Binary)
**Method**: Direct HCI socket access
```c
// From ble-scan.c
hci_sock = hci_open_dev(id);  // Opens /dev/hci0 directly
hci_le_set_scan_enable(dev->sock, 1, 0, 1000);  // Hardware-level command
```

**How it works**:
- Opens a raw HCI socket to `/dev/hci0`
- Sends **LE Set Scan Enable** commands directly to Bluetooth hardware
- Reads raw HCI events from the socket
- **Passive scanning** at hardware level
- Does NOT use BlueZ D-Bus API

### 2. dbus-victron-orion-tr (Python/Bleak)
**Method**: BlueZ D-Bus API
```python
scanner = BleakScanner(detection_callback=self.advertisement_callback)
await scanner.start()  # Calls BlueZ via D-Bus
```

**How it works**:
- Communicates with `bluetoothd` daemon via D-Bus
- BlueZ manages the actual HCI communication
- Receives advertisements through D-Bus signals
- **Passive scanning** at D-Bus level
- Does NOT directly touch HCI hardware

## Why They Can Coexist

```
┌─────────────────────────────────────────┐
│         Bluetooth Hardware              │
│            (hci0 adapter)               │
└────────────┬────────────────────────────┘
             │
             │ BLE Advertisements (broadcast)
             │
      ┌──────┴──────┐
      │             │
      ▼             ▼
┌──────────┐  ┌──────────────┐
│ HCI      │  │ bluetoothd   │
│ Socket   │  │ (BlueZ)      │
│          │  │              │
│ dbus-ble-│  │ Manages      │
│ sensors  │  │ D-Bus API    │
└──────────┘  └──────┬───────┘
                     │
                     │ D-Bus Signals
                     │
              ┌──────┴────────┐
              │               │
              ▼               ▼
         ┌─────────┐    ┌─────────┐
         │ Bleak   │    │ Other   │
         │ Scanner │    │ Clients │
         │         │    │         │
         │ orion-tr│    │         │
         └─────────┘    └─────────┘
```

**Key Points**:
1. **Different interfaces**: One uses HCI socket, one uses D-Bus
2. **Both passive**: Neither tries to control scan parameters exclusively
3. **Shared hardware**: Both read from the same advertisement stream
4. **No conflicts**: They're not competing for the same resource

## Why Active Scanning Causes Conflicts

When we tried **active scanning** (start/stop cycles):
```python
# This CONFLICTS
while True:
    await scanner.start()  # Tries to START discovery
    await asyncio.sleep(1)
    await scanner.stop()   # Tries to STOP discovery
```

**Problem**: `scanner.start()` tries to call BlueZ's `StartDiscovery()` method, which:
- Attempts to change HCI scan parameters
- Conflicts with `dbus-ble-sensors` which already has scan enabled
- Results in "Operation already in progress" error

## The Solution: Passive Continuous Scanning

```python
# This WORKS
scanner = BleakScanner(detection_callback=callback)
await scanner.start()  # Start ONCE
while True:
    await asyncio.sleep(60)  # Just keep alive
```

**Why it works**:
- Scanner starts once and stays passive
- Just listens to D-Bus signals from BlueZ
- Doesn't try to control scan parameters
- BlueZ is already scanning (due to `dbus-ble-sensors`)
- Multiple D-Bus clients can listen to the same signals

## Verification

```bash
# Check BlueZ discovery state
python3 << 'EOF'
import dbus
bus = dbus.SystemBus()
adapter = bus.get_object('org.bluez', '/org/bluez/hci0')
props = dbus.Interface(adapter, 'org.freedesktop.DBus.Properties')
print(f'Discovering: {props.Get("org.bluez.Adapter1", "Discovering")}')
EOF
# Output: Discovering: 0
```

**Result**: BlueZ reports NOT in active discovery, but both services receive advertisements!

This is because:
- `dbus-ble-sensors` has enabled scanning at HCI level
- BlueZ sees the scan is active and forwards advertisements via D-Bus
- Our service receives them passively through D-Bus signals

## Conclusion

**Multiple BLE scanners CAN coexist when**:
1. They use **different interfaces** (HCI socket vs D-Bus)
2. They use **passive scanning** (listen-only mode)
3. They don't try to **control scan parameters** exclusively

**Our implementation works because**:
- We use Bleak's passive continuous scanning
- We just listen to D-Bus advertisement signals
- We don't compete with `dbus-ble-sensors` for HCI control
- Both can read from the same advertisement stream simultaneously

This is actually the **ideal architecture** for BLE monitoring on Linux!

