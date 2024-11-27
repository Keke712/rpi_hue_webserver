import os
import sys
import asyncio
import logging
import configparser
from typing import List, Optional, Tuple

import controls
from flask import Flask, render_template, request, redirect, url_for, abort, jsonify, flash
from flask_cors import CORS
from errors import (
    DEVICE_NOT_FOUND, CONNECTION_ERROR, DISCONNECTION_ERROR, RECONNECT_ERROR,
    WRITE_ERROR, STATE_READ_ERROR, INVALID_BRIGHTNESS, INVALID_RGB_COLOR,
    PROFILE_NOT_FOUND, STATE_RETRIEVAL_ERROR, SUCCESS_CONNECTION, FAILED_CONNECTION,
    LAMP_NOT_CONNECTED, TURN_OFF_LOG, TURN_ON_LOG, SET_COLOR_LOG, SET_BRIGHTNESS_LOG,
    MISSING_BLUETOOTH_CONFIG
)
from config import set_mode_config

# Configuration des logs
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

MODES_CONFIG_PATH = 'modes.config'

class BluetoothLightController:
    def __init__(self, 
                 address: str, 
                 light_char: str, 
                 brightness_char: str, 
                 temperature_char: str, 
                 color_char: str):
        """
        Initialise le contrôleur pour le périphérique Bluetooth.
        
        :param address: Adresse MAC du périph��rique
        """
        self.ADDRESS = address
        self.LIGHT_CHARACTERISTIC = light_char
        self.BRIGHTNESS_CHARACTERISTIC = brightness_char
        self.TEMPERATURE_CHARACTERISTIC = temperature_char
        self.COLOR_CHARACTERISTIC = color_char
        
        self.adapter = None
        self.device = None
        self.service_uuid = None
        self.scanned_devices = []  # Nouvelle variable pour stocker les résultats du scan

    @staticmethod
    def convert_rgb(rgb: List[int]) -> List[int]:
        """
        Convertit un tableau RGB en format compatible avec le périphérique.
        
        :param rgb: Liste des valeurs R, G, B
        :return: Tableau converti
        """
        scale = 0xFF
        adjusted = [max(1, chan) for chan in rgb]
        total = sum(adjusted)
        adjusted = [int(round(chan / total * scale)) for chan in adjusted]
        return [0x1, adjusted[0], adjusted[2], adjusted[1]]

    @staticmethod
    def convert_rgb_back(rgb: List[int]) -> List[int]:
        """
        Convertit un tableau RGB du format compatible avec le périphérique en format standard.
        
        :param rgb: Liste des valeurs R, G, B
        :return: Tableau converti
        """
        return [rgb[1], rgb[3], rgb[2]]

    @staticmethod
    def hex_to_rgb(value: str) -> Tuple[int, int, int]:
        """
        Convertit une couleur hexadécimale en RGB.
        
        :param value: Couleur au format hexadécimale
        :return: Tuple RGB
        """
        value = value.lstrip('#')
        lv = len(value)
        return tuple(int(value[i:i + lv // 3], 16) for i in range(0, lv, lv // 3))

    async def connect(self) -> bool:
        """
        Établit une connexion avec le périphérique Bluetooth.
        
        :return: True si la connexion est réussie, False sinon
        """
        try:
            if not self.adapter:
                self.adapter = controls.Adapter()
            
            # Utilise les résultats du scan précédent s'ils existent
            devices = self.scanned_devices if self.scanned_devices else list(self.adapter.scan_devices())
            
            self.device = self.adapter.select_device(devices, self.ADDRESS)
            if not self.device:
                logger.error(DEVICE_NOT_FOUND.format(address=self.ADDRESS))
                return False

            self.adapter.connect(self.device)
            services = self.adapter.scan_services(self.device)
            self.service_uuid = self.adapter.get_uuid_by_char(
                self.device, services, self.LIGHT_CHARACTERISTIC
            )
            
            logger.info(f"Connecté au périphérique {self.ADDRESS}")
            return True
        except Exception as e:
            logger.error(CONNECTION_ERROR.format(error=e))
            return False

    async def disconnect(self):
        """
        Déconnecte le périphérique Bluetooth.
        """
        if self.adapter and self.device:
            try:
                self.adapter.disconnect(self.device)
                logger.info("Périphérique déconnecté")
            except Exception as e:
                logger.error(DISCONNECTION_ERROR.format(error=e))

    async def turn_off(self):
        """Éteint le périphérique."""
        if not self.adapter or not self.device:
            abort(400, description=LAMP_NOT_CONNECTED)
        await self._write(self.LIGHT_CHARACTERISTIC, b"\x00", TURN_OFF_LOG)

    async def turn_on(self):
        """Allume le périphérique."""
        if not self.adapter or not self.device:
            abort(400, description=LAMP_NOT_CONNECTED)
        await self._write(self.LIGHT_CHARACTERISTIC, b"\x01", TURN_ON_LOG)

    async def put_color(self, r: int, g: int, b: int):
        """
        Définit la couleur du périphérique.
        
        :param r: Composante rouge
        :param g: Composante verte
        :param b: Composante bleue
        """
        if not self.adapter or not self.device:
            abort(400, description=LAMP_NOT_CONNECTED)
        rgb_bytes = bytes(self.convert_rgb([r, g, b]))
        await self._write(self.COLOR_CHARACTERISTIC, rgb_bytes, SET_COLOR_LOG.format(r=r, g=g, b=b))

    async def put_brightness(self, brightness: int):
        """
        Définit la luminosité du périphérique.
        
        :param brightness: Niveau de luminosité (0-100)
        """
        if not self.adapter or not self.device:
            abort(400, description=LAMP_NOT_CONNECTED)
        if not 0 <= brightness <= 100:
            logger.warning(INVALID_BRIGHTNESS.format(brightness=brightness))
            return

        brightness_byte = int(brightness * 2.55)
        await self._write(self.BRIGHTNESS_CHARACTERISTIC, bytes([brightness_byte]), SET_BRIGHTNESS_LOG.format(brightness=brightness))

    async def _write(self, characteristic: str, data: bytes, log_message: str):
        """
        Écrit des données.
        
        :param characteristic: Caractéristique à écrire
        :param data: Données à écrire
        :param log_message: Message de log
        """
        try:
            logger.info(log_message)
            self.adapter.write(self.device, self.service_uuid, characteristic, data)
        except Exception as e:
            logger.error(WRITE_ERROR.format(error=e))

    async def get_state(self) -> Optional[dict]:
        """
        Récupère l'état actuel du périphérique.
        
        :return: Dictionnaire contenant l'état du périphérique ou None en cas d'erreur
        """
        if not self.adapter or not self.device:
            return {"connected": False}

        try:
            light_state = self.adapter.read(self.device, self.service_uuid, self.LIGHT_CHARACTERISTIC)
            brightness = self.adapter.read(self.device, self.service_uuid, self.BRIGHTNESS_CHARACTERISTIC)
            color = self.adapter.read(self.device, self.service_uuid, self.COLOR_CHARACTERISTIC)
            identifier = self.device.identifier()
            brightness_percentage = int.from_bytes(brightness, byteorder='big') / 2.55
            r, g, b = self.convert_rgb_back(list(color))  # Convert RGB values back to standard format
            return {
                "connected": True,
                "light_state": light_state,
                "brightness": round(brightness_percentage),
                "color": {"r": r, "g": g, "b": b},
                "identifier": identifier
            }
        except Exception as e:
            logger.error(STATE_READ_ERROR.format(error=e))
            return {"connected": False}

    def scan_devices(self):
        """
        Scanne les périphériques Bluetooth à proximité.
        
        :return: Liste des périphériques trouvés
        """
        if not self.adapter:
            self.adapter = controls.Adapter()
        self.scanned_devices = self.adapter.scan_devices()  # Sauvegarde les résultats
        return self.scanned_devices

def create_app():
    """
    Crée et configure l'application Flask.
    
    :return: Application Flask configurée
    """
    app = Flask(__name__)
    app.secret_key = 'your_secret_key'  # Needed for flashing messages
    CORS(app)

    # Read Bluetooth address from config
    config = configparser.ConfigParser()
    config.read(MODES_CONFIG_PATH)
    
    if 'BLUETOOTH' not in config:
        raise ValueError(MISSING_BLUETOOTH_CONFIG)
    
    bluetooth_address = config['BLUETOOTH']['address']
    
    # Initialisation du contrôleur
    controller = BluetoothLightController(
        address=bluetooth_address,
        light_char="932c32bd-0002-47a2-835a-a8d455b859dd",
        brightness_char="932c32bd-0003-47a2-835a-a8d455b859dd",
        temperature_char="932c32bd-0004-47a2-835a-a8d455b859dd",
        color_char="932c32bd-0005-47a2-835a-a8d455b859dd"
    )

    @app.route('/')
    async def main():
        # Render the page first
        response = render_template('index.html', mac_address=controller.ADDRESS, devices=[])
        
        # Perform the device scan asynchronously
        if not controller.scanned_devices:
            controller.scanned_devices = controller.scan_devices()
        
        devices_info = [{"address": device.address(), "identifier": device.identifier()} for device in controller.scanned_devices]
        
        # Update the page with the scanned devices
        return render_template('index.html', mac_address=controller.ADDRESS, devices=devices_info)

    @app.route('/connect')
    async def run_connect():
        address = request.args.get('address', controller.ADDRESS)
        from_main = request.args.get('from_main', False)
        controller.ADDRESS = address  # Update the controller's address
        success = await controller.connect()
        if from_main:
            if success:
                flash('Lampe connectée avec succès!', 'success')
            else:
                flash('Échec de la connexion', 'danger')
            return redirect(url_for('main'))
        else:
            if success:
                return jsonify({'status': 'success'})
            return jsonify({'status': 'error'})

    @app.route('/off')
    async def run_off():
        await controller.turn_off()
        return jsonify({'status': 'success', 'message': 'Device turned off'})

    @app.route('/on')
    async def run_on():
        await controller.turn_on()
        return jsonify({'status': 'success', 'message': 'Device turned on'})

    @app.route('/color')
    async def run_color():
        rgb = request.args.get('rgb', '').split(',')
        try:
            rgb = [int(x) for x in rgb]
            await controller.put_color(rgb[0], rgb[1], rgb[2])
            return jsonify({'status': 'success', 'message': f'Color set to RGB({rgb[0]}, {rgb[1]}, {rgb[2]})'})
        except (ValueError, IndexError):
            logger.error(INVALID_RGB_COLOR)
            return jsonify({'status': 'error', 'message': INVALID_RGB_COLOR})

    @app.route('/brightness')
    async def run_brightness():
        try:
            bright = int(request.args.get('p', 50))
            await controller.put_brightness(bright)
            return jsonify({'status': 'success', 'message': f'Brightness set to {bright}%'})
        except ValueError:
            logger.error(INVALID_BRIGHTNESS.format(brightness=bright))
            return jsonify({'status': 'error', 'message': INVALID_BRIGHTNESS.format(brightness=bright)})

    @app.route('/state')
    async def run_state():
        state = await controller.get_state()
        if state is None:
            abort(500, description=STATE_RETRIEVAL_ERROR)
        # Convert bytes to a JSON serializable format if connected
        if state.get("connected"):
            state['light_state'] = state['light_state'].hex()
        return jsonify(state)

    @app.route('/set_mode', methods=['POST'])
    async def set_mode():
        profile = request.args.get('profile', 'MODE1')
        config = configparser.ConfigParser()
        config.read(MODES_CONFIG_PATH)

        if profile not in config:
            return jsonify({'status': 'error', 'message': PROFILE_NOT_FOUND})

        try:
            # Convert light_state from string to bytes
            light_state = bytes.fromhex(config[profile]['light_state'])
            brightness = int(config[profile]['brightness'])
            
            # Parse the color dictionary string
            color_str = config[profile]['color']
            # Convert string representation of dict to actual dict
            color_dict = eval(color_str)
            r = color_dict['r']
            g = color_dict['g']
            b = color_dict['b']

            # Set light state
            if light_state == b'\x01':
                await controller.turn_on()
            else:
                await controller.turn_off()

            # Set brightness
            await controller.put_brightness(brightness)

            # Set color
            await controller.put_color(r, g, b)

            return jsonify({'status': 'success', 'message': f'Mode {profile} set successfully'})
        except Exception as e:
            return jsonify({'status': 'error', 'message': f'Failed to set mode: {str(e)}'})

    @app.route('/create_mode', methods=['POST'])
    async def create_mode():
        profile = request.form.get('profile')
        if not profile:
            abort(400, description="Profile name is required")

        # Get current state from the device
        current_state = await controller.get_state()
        if not current_state or not current_state.get('connected'):
            return jsonify({'status': 'error', 'message': 'Device not connected'})

        # Format the state according to modes.config format
        state = {
            'light_state': current_state['light_state'].hex(),  # Convert bytes to hex string
            'brightness': str(current_state['brightness']),
            'color': str({'r': current_state['color']['r'], 
                         'g': current_state['color']['g'], 
                         'b': current_state['color']['b']})
        }

        set_mode_config(profile, state)
        return jsonify({'status': 'success', 'message': f'Mode {profile} created successfully'})

    @app.route('/scan')
    async def run_scan():
        devices = controller.scan_devices()
        devices_info = [{"address": device.address(), "identifier": device.identifier()} for device in devices]
        return jsonify({"devices": devices_info})

    @app.route('/get_modes')
    async def get_modes():
        config = configparser.ConfigParser()
        config.read(MODES_CONFIG_PATH)

        modes = {}
        for section in config.sections():
            if section != 'BLUETOOTH':
                modes[section] = {
                    'brightness': config[section].get('brightness', None),
                    'color': config[section].get('color', None),
                    'light_state': config[section].get('light_state', None)
                }

        if not modes:
            return jsonify({"modes": False})
        return jsonify({"modes": True, "data": modes})

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host=os.getenv('APP_HOST', '192.168.0.11'), debug=True)