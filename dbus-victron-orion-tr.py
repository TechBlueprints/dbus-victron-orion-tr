#!/usr/bin/env python3
"""
Victron Orion-TR Smart DC-DC Converter D-Bus Service

This service scans for Victron Orion-TR Smart devices via Bluetooth LE,
decrypts their advertisement data, and publishes the values to D-Bus.

Requirements:
- victron_ble library (for decoding)
- bleak library (for BLE scanning)
- velib_python (for D-Bus integration)
"""

import asyncio
import sys
import os
import logging
import configparser
from typing import Dict, Optional
from datetime import datetime, timedelta
import dbus
import dbus.mainloop.glib
from gi.repository import GLib

# Add ext directory to path
sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'ext'))
sys.path.insert(1, os.path.join(os.path.dirname(__file__), 'ext', 'velib_python'))

from bleak import BleakScanner, BleakError
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from victron_ble.devices import detect_device_type
from victron_ble.exceptions import AdvertisementKeyMismatchError

# Import velib_python for D-Bus
from vedbus import VeDbusService
from settingsdevice import SettingsDevice

# Set up D-Bus main loop
dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)

# Victron manufacturer ID
VICTRON_MANUFACTURER_ID = 0x02E1

# Load configuration
def load_config():
    """Load device configuration from config.ini"""
    config_path = os.path.join(os.path.dirname(__file__), 'config.ini')
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Please copy config.default.ini to config.ini and edit with your device details."
        )
    
    config = configparser.ConfigParser()
    config.read(config_path)
    
    # Parse device configurations
    devices = {}
    device_timeout = config.getint('DEFAULT', 'DEVICE_TIMEOUT', fallback=60)
    log_level = config.get('DEFAULT', 'LOG_LEVEL', fallback='INFO').upper()
    
    for section in config.sections():
        if section.startswith('DEVICE_'):
            try:
                mac = config.get(section, 'MAC').strip().lower()
                key = config.get(section, 'KEY').strip().lower()
                instance = config.getint(section, 'INSTANCE')
                
                # Validate MAC address format
                if len(mac.replace(':', '')) != 12:
                    raise ValueError(f"Invalid MAC address in {section}: {mac}")
                
                # Validate encryption key format
                if len(key) != 32:
                    raise ValueError(f"Invalid encryption key in {section}: must be 32 hex characters")
                
                devices[mac] = {
                    "key": key,
                    "dbus_instance": instance,
                }
                
            except (configparser.NoOptionError, ValueError) as e:
                logging.warning(f"Skipping {section}: {e}")
                continue
    
    if not devices:
        raise ValueError("No valid devices found in config.ini")
    
    return devices, device_timeout, log_level

# Load devices from config
DEVICES, DEVICE_TIMEOUT, LOG_LEVEL = load_config()

logging.basicConfig(level=getattr(logging, LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)


# Map Victron operation modes to D-Bus /State values
# Based on OperationMode enum values from victron_ble
OPERATION_MODE_MAP = {
    "OperationMode.OFF": 0,
    "OperationMode.POWER_SUPPLY": 11,  # DC-DC Power Supply mode
    "OperationMode.BULK": 3,
    "OperationMode.ABSORPTION": 4,
    "OperationMode.FLOAT": 5,
    "OperationMode.STORAGE": 6,
    "OperationMode.EXTERNAL_CONTROL": 252,
}

# Fallback product names for Orion-TR ProductIds not in victron_ble library
ORION_TR_PRODUCT_NAMES = {
    0xA3C0: "Orion-TR Smart 12/12-18A",
    0xA3C1: "Orion-TR Smart 12/24-10A",
    0xA3C2: "Orion-TR Smart 12/48-6A",
    0xA3D0: "Orion-TR Smart 24/12-20A",
    0xA3D1: "Orion-TR Smart 24/24-12A",
    0xA3D2: "Orion-TR Smart 24/48-6A",
    0xA3D5: "Orion-TR Smart 48/24-12A",
    0xA3D6: "Orion-TR Smart 48/48-6A",
}


class OrionTRDevice:
    """Represents a single Orion-TR device"""
    
    def __init__(self, mac: str, encryption_key: str, dbus_instance: int):
        self.mac = mac.lower()
        self.encryption_key = encryption_key
        self.dbus_instance = dbus_instance  # Initial instance from config
        
        # Device info from BLE
        self.ble_name: Optional[str] = None  # Name from Bluetooth device
        self.model_name: Optional[str] = None  # From decrypted data
        self.product_id: Optional[int] = None  # Product ID from BLE advertisement
        
        # Cached values
        self.input_voltage: Optional[float] = None
        self.output_voltage: Optional[float] = None
        self.charge_state: Optional[str] = None
        self.charger_error: Optional[int] = None
        self.off_reason: Optional[int] = None
        self.last_update: Optional[datetime] = None
        
        # D-Bus service
        self.dbus_service: Optional[VeDbusService] = None
        self.settings_device: Optional[SettingsDevice] = None
        
        # Service type determination (set after first advertisement)
        self.service_type: Optional[str] = None  # 'dcdc' or 'alternator'
        
    @property
    def name(self) -> str:
        """Return device name (BLE name or MAC)"""
        return self.ble_name or self.mac
    
    @property
    def is_connected(self) -> bool:
        """Check if device is connected (received data recently)"""
        if not self.last_update:
            return False
        return (datetime.now() - self.last_update) < timedelta(seconds=DEVICE_TIMEOUT)
    
    def _determine_service_type(self, operation_mode: str) -> str:
        """Determine D-Bus service type based on operation mode
        
        Args:
            operation_mode: The operation mode string (e.g., "OperationMode.POWER_SUPPLY")
            
        Returns:
            'dcdc' for Power Supply mode, 'alternator' for Charger modes
        """
        # Charger modes: BULK, ABSORPTION, FLOAT, STORAGE
        charger_modes = [
            "OperationMode.BULK",
            "OperationMode.ABSORPTION", 
            "OperationMode.FLOAT",
            "OperationMode.STORAGE"
        ]
        
        if operation_mode in charger_modes:
            return 'alternator'
        else:
            # Default to dcdc for POWER_SUPPLY, OFF, and EXTERNAL_CONTROL
            return 'dcdc'
    
    def _get_device_instance(self, service_type: str):
        """Get device instance, checking settings first or finding an available one
        
        Args:
            service_type: Either 'dcdc' or 'alternator'
        """
        # Generate unique ID for this device
        mac_hex = self.mac.replace(':', '')
        mac_int = int(mac_hex, 16)
        mac_b36 = self._to_base36(mac_int)
        unique_id = f"tr_{mac_b36}"
        settings_path = f"/Settings/Devices/{unique_id}/ClassAndVrmInstance"
        
        try:
            # Check if this device already has a saved instance in settings
            bus = dbus.SystemBus()
            obj = bus.get_object('com.victronenergy.settings', settings_path)
            iface = dbus.Interface(obj, 'com.victronenergy.BusItem')
            value = iface.GetValue()
            
            # Parse "dcdc:X" or "alternator:X" format
            if value and ':' in value:
                parts = value.split(':')
                if len(parts) == 2 and parts[0] == service_type:
                    instance = int(parts[1])
                    logger.info(f"{self.mac}: Found existing {service_type} instance {instance} in settings")
                    return instance
                elif len(parts) == 2:
                    # Settings exist but for different service type - will be cleaned up
                    logger.info(f"{self.mac}: Found settings for {parts[0]}, but need {service_type} - will reassign")
        except Exception as e:
            logger.debug(f"{self.mac}: No existing settings found: {e}")
        
        # No existing settings, check if configured instance is available
        try:
            bus = dbus.SystemBus()
            settings = bus.get_object('com.victronenergy.settings', '/Settings')
            iface = dbus.Interface(settings, 'com.victronenergy.BusItem')
            
            # Get all device instances currently in use for this service type
            used_instances = set()
            devices_obj = bus.get_object('com.victronenergy.settings', '/Settings/Devices')
            devices_iface = dbus.Interface(devices_obj, 'com.victronenergy.BusItem')
            devices = devices_iface.GetValue()
            
            for device_path in devices:
                if device_path.endswith('/ClassAndVrmInstance'):
                    try:
                        obj = bus.get_object('com.victronenergy.settings', f'/Settings/Devices/{device_path}')
                        iface = dbus.Interface(obj, 'com.victronenergy.BusItem')
                        value = iface.GetValue()
                        if value and ':' in value:
                            parts = value.split(':')
                            if len(parts) == 2 and parts[0] == service_type:
                                used_instances.add(int(parts[1]))
                    except:
                        pass
            
            # Check if our configured instance is free
            if self.dbus_instance not in used_instances:
                logger.info(f"{self.mac}: Using configured {service_type} instance {self.dbus_instance}")
                return self.dbus_instance
            
            # Find first available instance starting from configured value
            for instance in range(self.dbus_instance, 300):
                if instance not in used_instances:
                    logger.info(f"{self.mac}: Configured instance {self.dbus_instance} in use, using {instance}")
                    return instance
                    
        except Exception as e:
            logger.warning(f"{self.mac}: Error checking device instances: {e}, using configured instance {self.dbus_instance}")
            return self.dbus_instance
        
        # Fallback to configured instance
        logger.warning(f"{self.mac}: Could not find free instance, using configured {self.dbus_instance}")
        return self.dbus_instance
    
    def initialize_dbus(self, service_type: str):
        """Initialize D-Bus service for this device
        
        Args:
            service_type: Either 'dcdc' for Power Supply mode or 'alternator' for Charger mode
        """
        self.service_type = service_type
        
        # Get the device instance (from settings or find available)
        self.dbus_instance = self._get_device_instance(service_type)
        
        # Convert MAC address to base36 for compact service naming
        # MAC address is 6 bytes (48 bits) - convert to integer then base36
        mac_hex = self.mac.replace(':', '')
        mac_int = int(mac_hex, 16)
        # Convert to base36 (0-9, a-z)
        mac_b36 = self._to_base36(mac_int)
        service_name = f"com.victronenergy.{service_type}.tr_{mac_b36}"
        
        logger.info(f"{self.name}: Initializing D-Bus service {service_name} with instance {self.dbus_instance}")
        
        # Each service needs its own D-Bus connection to avoid path conflicts
        # Create a new private connection (not the singleton SystemBus)
        bus = dbus.bus.BusConnection(dbus.bus.BusConnection.TYPE_SYSTEM)
        self.dbus_service = VeDbusService(service_name, bus=bus, register=False)
        
        # Add mandatory paths
        self.dbus_service.add_path('/Mgmt/ProcessName', __file__)
        self.dbus_service.add_path('/Mgmt/ProcessVersion', '1.0')
        self.dbus_service.add_path('/Mgmt/Connection', 'Bluetooth LE')
        
        # Device information
        self.dbus_service.add_path('/DeviceInstance', self.dbus_instance)
        self.dbus_service.add_path('/ProductId', None,
            gettextcallback=lambda p, v: f"0x{v:04X}" if v is not None else "")  # Format as hex
        self.dbus_service.add_path('/ProductName', None)
        self.dbus_service.add_path('/CustomName', None)
        self.dbus_service.add_path('/FirmwareVersion', None)  # Not available from BLE
        self.dbus_service.add_path('/HardwareVersion', None)  # Not available from BLE
        self.dbus_service.add_path('/Serial', self.mac.replace(':', '').upper())  # Use MAC as serial
        self.dbus_service.add_path('/Connected', 0)
        
        # Capabilities - use same bitmask as Orion XS
        # This tells the UI what features are available
        self.dbus_service.add_path('/Capabilities/Capabilities1', 1342292476)
        
        # Input voltage, current, and power (from alternator/battery)
        self.dbus_service.add_path('/Dc/In/V', None)
        self.dbus_service.add_path('/Dc/In/I', None)  # Not available from Orion-TR
        self.dbus_service.add_path('/Dc/In/P', None)  # Not available from Orion-TR
        
        # Output voltage and current (to battery)
        self.dbus_service.add_path('/Dc/0/Voltage', None)
        self.dbus_service.add_path('/Dc/0/Current', 0.0)  # Not available from Orion-TR
        self.dbus_service.add_path('/Dc/0/Power', 0.0)    # Not available from Orion-TR
        
        # State and error information
        self.dbus_service.add_path('/State', 0)
        self.dbus_service.add_path('/ErrorCode', 0)
        self.dbus_service.add_path('/DeviceOffReason', 0)
        
        # Mode: Don't publish /Mode path since we can't control Orion-TR remotely via BLE
        # This will hide the Switch control in the UI
        
        # Register the service after adding all paths
        self.dbus_service.register()
        
        # Register device in settings for GUI device list
        self._register_device_settings()
        
        logger.info(f"{self.name}: D-Bus service initialized")
    
    def _register_device_settings(self):
        """Register device in com.victronenergy.settings for GUI device list"""
        try:
            # Use same base36 MAC identifier as service name for consistency
            mac_hex = self.mac.replace(':', '')
            mac_int = int(mac_hex, 16)
            mac_b36 = self._to_base36(mac_int)
            unique_id = f"tr_{mac_b36}"
            settings_path = f"/Settings/Devices/{unique_id}"
            
            # Create ClassAndVrmInstance setting
            # Use the current service type (dcdc or alternator)
            class_and_vrm_instance = f"{self.service_type}:{self.dbus_instance}"
            
            # Use SettingsDevice to register the device
            # This makes it appear in the GUI device list
            settings = {
                "ClassAndVrmInstance": [
                    f"{settings_path}/ClassAndVrmInstance",
                    class_and_vrm_instance,
                    0,
                    0,
                ],
            }
            
            # Get the D-Bus connection from our service
            bus = self.dbus_service._dbusconn
            
            # Initialize SettingsDevice (will create the settings if they don't exist)
            self.settings_device = SettingsDevice(
                bus,
                settings,
                eventCallback=None,  # No callback needed for now
                timeout=10
            )
            
            logger.info(f"{self.name}: Registered device settings: {settings_path}/ClassAndVrmInstance = {class_and_vrm_instance}")
            
        except Exception as e:
            logger.error(f"{self.name}: Failed to register device settings: {e}")
            # Don't fail the whole service if settings registration fails
    
    @staticmethod
    def _to_base36(num: int) -> str:
        """Convert an integer to base36 string (0-9, a-z)"""
        if num == 0:
            return '0'
        digits = '0123456789abcdefghijklmnopqrstuvwxyz'
        result = ''
        while num:
            result = digits[num % 36] + result
            num //= 36
        return result
    
    def update_from_advertisement(self, manufacturer_data: bytes) -> bool:
        """
        Decode advertisement data and update cached values.
        Returns True if successful, False otherwise.
        """
        try:
            # Extract product ID from advertisement (bytes 2-3, little-endian)
            import struct
            if len(manufacturer_data) >= 4:
                self.product_id = struct.unpack("<H", manufacturer_data[2:4])[0]
            
            # Detect device type
            device_parser = detect_device_type(manufacturer_data)
            if not device_parser:
                logger.debug(f"{self.name}: Could not detect device type")
                return False
            
            # Parse with encryption key
            parser = device_parser(self.encryption_key)
            parsed = parser.parse(manufacturer_data)
            
            # Update cached values
            self.input_voltage = parsed.get_input_voltage()
            self.output_voltage = parsed.get_output_voltage()
            self.charge_state = str(parsed.get_charge_state())
            
            # Get error code and off reason as integers
            charger_error = parsed.get_charger_error()
            self.charger_error = charger_error.value if charger_error else 0
            
            off_reason = parsed.get_off_reason()
            self.off_reason = off_reason.value if off_reason else 0
            
            self.model_name = parsed.get_model_name()
            self.last_update = datetime.now()
            
            logger.info(
                f"{self.name}: IN={self.input_voltage}V OUT={self.output_voltage}V "
                f"STATE={self.charge_state} ERR={self.charger_error} PID=0x{self.product_id:04X}"
            )
            
            # Determine what service type we should be using based on operation mode
            needed_service_type = self._determine_service_type(self.charge_state)
            
            # If service not initialized yet, or mode changed, (re)initialize
            if self.service_type != needed_service_type:
                if self.dbus_service:
                    logger.info(f"{self.name}: Mode changed from {self.service_type} to {needed_service_type}, reinitializing D-Bus service")
                    # Unregister old service
                    try:
                        self.dbus_service.__del__()
                    except:
                        pass
                    self.dbus_service = None
                    self.settings_device = None
                
                # Initialize with new service type
                self.initialize_dbus(needed_service_type)
            
            # Publish to D-Bus
            self.publish_to_dbus()
            
            return True
            
        except AdvertisementKeyMismatchError:
            logger.warning(f"{self.name}: Incorrect advertisement key")
            return False
        except Exception as e:
            logger.error(f"{self.name}: Error decoding advertisement: {e}")
            return False
    
    def publish_to_dbus(self):
        """Publish current values to D-Bus"""
        if not self.dbus_service:
            return
        
        try:
            # Update device info
            if self.ble_name:
                self.dbus_service['/CustomName'] = self.ble_name
            
            # ProductName: Use fallback if victron_ble library doesn't know this ProductId
            if self.model_name and not self.model_name.startswith('<Unknown device:'):
                self.dbus_service['/ProductName'] = self.model_name
            elif self.product_id in ORION_TR_PRODUCT_NAMES:
                self.dbus_service['/ProductName'] = ORION_TR_PRODUCT_NAMES[self.product_id]
            elif self.model_name:
                self.dbus_service['/ProductName'] = self.model_name  # Keep the <Unknown device: X> as fallback
            
            # ProductId: Use real ProductId for dcdc mode, Orion XS ProductId for alternator mode
            if self.product_id is not None:
                if self.service_type == 'alternator':
                    # Use Orion XS ProductId (0xA3F0) so UI treats it like an Orion XS
                    self.dbus_service['/ProductId'] = 0xA3F0
                else:
                    # Use real Orion-TR ProductId for dcdc mode
                    self.dbus_service['/ProductId'] = self.product_id
            
            # Update connection status
            self.dbus_service['/Connected'] = 1 if self.is_connected else 0
            
            # Update voltages
            if self.input_voltage is not None:
                self.dbus_service['/Dc/In/V'] = self.input_voltage
            if self.output_voltage is not None:
                self.dbus_service['/Dc/0/Voltage'] = self.output_voltage
            
            # Update state (map operation mode to D-Bus state value)
            if self.charge_state:
                state_value = OPERATION_MODE_MAP.get(self.charge_state, 0)
                self.dbus_service['/State'] = state_value
            
            # Update error codes
            if self.charger_error is not None:
                self.dbus_service['/ErrorCode'] = self.charger_error
            
            if self.off_reason is not None:
                self.dbus_service['/DeviceOffReason'] = self.off_reason
            
            # Current and Power are not available from Orion-TR
            self.dbus_service['/Dc/0/Current'] = None
            self.dbus_service['/Dc/0/Power'] = None
            
        except Exception as e:
            logger.error(f"{self.name}: Error publishing to D-Bus: {e}")


class OrionTRScanner:
    """Scans for Orion-TR devices and manages their D-Bus services"""
    
    def __init__(self):
        self.devices: Dict[str, OrionTRDevice] = {}
        
        # Initialize devices from configuration
        # Don't initialize D-Bus yet - wait for first advertisement to determine service type
        for mac, config in DEVICES.items():
            device = OrionTRDevice(
                mac=mac,
                encryption_key=config["key"],
                dbus_instance=config["dbus_instance"],
            )
            self.devices[mac.lower()] = device
            logger.info(f"Configured device: {mac} (will initialize D-Bus after first advertisement)")
    
    def advertisement_callback(self, device: BLEDevice, advertisement_data: AdvertisementData):
        """Called when a BLE advertisement is received"""
        
        # Check if this is a Victron device
        if VICTRON_MANUFACTURER_ID not in advertisement_data.manufacturer_data:
            return
        
        # Check if this is one of our configured devices
        mac = device.address.lower()
        if mac not in self.devices:
            return
        
        # Get manufacturer data
        mfg_data = advertisement_data.manufacturer_data[VICTRON_MANUFACTURER_ID]
        
        # Update device from advertisement
        orion_device = self.devices[mac]
        
        # Update BLE name from the device (first time or if changed)
        if device.name and device.name != orion_device.ble_name:
            orion_device.ble_name = device.name
            logger.info(f"Device {mac} identified as: {device.name}")
        
        orion_device.update_from_advertisement(mfg_data)
    
    async def scan_continuously(self):
        """Continuously scan for BLE advertisements"""
        logger.info("Starting continuous BLE scan...")
        scanner = BleakScanner(detection_callback=self.advertisement_callback)
        
        while True:
            try:
                await scanner.start()
                await asyncio.sleep(1)  # Scan for 1 second intervals
                await scanner.stop()
            except BleakError as e:
                logger.error(f"BLE scan error: {e}. Retrying in 5 seconds...")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"Unexpected error during BLE scan: {e}. Retrying in 5 seconds...")
                await asyncio.sleep(5)


def main():
    """Main entry point"""
    logger.info("=== Victron Orion-TR Smart D-Bus Service ===")
    logger.info(f"Configured devices: {len(DEVICES)}")
    
    # Create scanner
    scanner = OrionTRScanner()
    
    # Set up GLib main loop
    mainloop = GLib.MainLoop()
    
    # Create async event loop and integrate with GLib
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Schedule the BLE scanner as a background task
    def start_ble_scanner():
        asyncio.ensure_future(scanner.scan_continuously(), loop=loop)
        return False  # Don't repeat
    
    # Schedule BLE scanner to start after a short delay
    GLib.idle_add(start_ble_scanner)
    
    # Schedule async event loop processing
    def process_async():
        loop.run_until_complete(asyncio.sleep(0))  # Process pending tasks
        return True  # Keep repeating
    
    GLib.timeout_add(100, process_async)  # Process every 100ms
    
    # Run the main loop (handles D-Bus and async tasks)
    try:
        logger.info("Starting main loop...")
        mainloop.run()
    except KeyboardInterrupt:
        logger.info("Service stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
