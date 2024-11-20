# Web server - Philips Hue Controller (made on Raspberry Pi)

This repository contains a web server for controlling Philips Hue lights using a Raspberry Pi.

## Main Script

The `main.py` script is the entry point of the application. It creates a Flask web application and defines routes to control the Philips Hue lights.

### Key Features

- **BluetoothLightController**: A class to manage the Bluetooth connection and control the lights.
  - `connect()`: Connects to the Bluetooth device.
  - `disconnect()`: Disconnects from the Bluetooth device.
  - `turn_off()`: Turns off the light.
  - `turn_on()`: Turns on the light.
  - `put_color(r, g, b)`: Sets the light color.
  - `put_brightness(brightness)`: Sets the brightness level.

- **Flask Routes**: 
  - `/`: Main page.
  - `/connect`: Connects to the Bluetooth device.
  - `/off`: Turns off the light.
  - `/on`: Turns on the light.
  - `/color`: Sets the light color.
  - `/brightness`: Sets the brightness level.

For more detailed information, please refer to the [main.py](https://github.com/Keke712/rpi_hue_webserver/blob/main/main.py) file.

## Controls

The `controls.py` script contains helper classes and methods to interface with the Bluetooth device.

### Key Features

- **Service**: A class to manage the Bluetooth service UUID and characteristic.
- **Adapter**: A class to manage the Bluetooth adapter and device connections.
  - `scan_devices()`: Scans for available Bluetooth devices.
  - `select_device(dlist, address)`: Selects a device by its address.
  - `connect(device)`: Connects to the selected device.
  - `scan_services(device)`: Scans for services on the device.
  - `get_uuid_by_char(device, slist, char)`: Gets the service UUID by characteristic.
  - `write(device, service_uuid, characteristic_uuid, content)`: Writes data to the device.
  - `read(device, service_uuid, characteristic_uuid)`: Reads data from the device.

For more detailed information, please refer to the [controls.py](https://github.com/Keke712/rpi_hue_webserver/blob/main/controls.py) file.