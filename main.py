import os
import sys
import asyncio
import logging
from typing import List, Optional, Tuple

import controls
from flask import Flask, render_template, request, redirect, url_for, abort

# Configuration des logs
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class BluetoothLightController:
    def __init__(self, 
                 address: str, 
                 light_char: str, 
                 brightness_char: str, 
                 temperature_char: str, 
                 color_char: str):
        """
        Initialise le contrôleur pour le périphérique Bluetooth.
        
        :param address: Adresse MAC du périphérique
        """
        self.ADDRESS = address
        self.LIGHT_CHARACTERISTIC = light_char
        self.BRIGHTNESS_CHARACTERISTIC = brightness_char
        self.TEMPERATURE_CHARACTERISTIC = temperature_char
        self.COLOR_CHARACTERISTIC = color_char
        
        self.adapter = None
        self.device = None
        self.service_uuid = None

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
    def hex_to_rgb(value: str) -> Tuple[int, int, int]:
        """
        Convertit une couleur hexadécimale en RGB.
        
        :param value: Couleur au format hexadécimal
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
            self.adapter = controls.Adapter()
            devices = list(self.adapter.scan_devices())
            
            self.device = self.adapter.select_device(devices, self.ADDRESS)
            if not self.device:
                logger.error(f"Périphérique {self.ADDRESS} non trouvé")
                return False

            self.adapter.connect(self.device)
            services = self.adapter.scan_services(self.device)
            self.service_uuid = self.adapter.get_uuid_by_char(
                self.device, services, self.LIGHT_CHARACTERISTIC
            )
            
            logger.info(f"Connecté au périphérique {self.ADDRESS}")
            return True
        except Exception as e:
            logger.error(f"Erreur de connexion : {e}")
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
                logger.error(f"Erreur lors de la déconnexion : {e}")

    async def turn_off(self):
        """Éteint le périphérique."""
        await self._write_with_reconnect(
            self.LIGHT_CHARACTERISTIC, b"\x00", 
            "Extinction du périphérique"
        )

    async def turn_on(self):
        """Allume le périphérique."""
        await self._write_with_reconnect(
            self.LIGHT_CHARACTERISTIC, b"\x01", 
            "Allumage du périphérique"
        )

    async def put_color(self, r: int, g: int, b: int):
        """
        Définit la couleur du périphérique.
        
        :param r: Composante rouge
        :param g: Composante verte
        :param b: Composante bleue
        """
        rgb_bytes = bytes(self.convert_rgb([r, g, b]))
        await self._write_with_reconnect(
            self.COLOR_CHARACTERISTIC, rgb_bytes, 
            f"Définition de la couleur RGB({r},{g},{b})"
        )

    async def put_brightness(self, brightness: int):
        """
        Définit la luminosité du périphérique.
        
        :param brightness: Niveau de luminosité (0-100)
        """
        if not 0 <= brightness <= 100:
            logger.warning(f"Luminosité invalide : {brightness}")
            return

        # Convertit le pourcentage en valeur compatible
        brightness_byte = int(brightness * 2.55)
        await self._write_with_reconnect(
            self.BRIGHTNESS_CHARACTERISTIC, 
            bytes([brightness_byte]), 
            f"Réglage luminosité à {brightness}%"
        )

    async def _write_with_reconnect(self, 
                                    characteristic: str, 
                                    data: bytes, 
                                    log_message: str):
        """
        Écrit des données avec reconnexion automatique si nécessaire.
        
        :param characteristic: Caractéristique à écrire
        :param data: Données à écrire
        :param log_message: Message de log
        """
        if not self.adapter:
            success = await self.connect()
            if not success:
                logger.error("Impossible de se reconnecter")
                return

        try:
            logger.info(log_message)
            self.adapter.write(
                self.device, 
                self.service_uuid, 
                characteristic, 
                data
            )
        except Exception as e:
            logger.error(f"Erreur d'écriture : {e}")
            await self.connect()

def create_app():
    """
    Crée et configure l'application Flask.
    
    :return: Application Flask configurée
    """
    app = Flask(__name__)
    
    # Initialisation du contrôleur
    controller = BluetoothLightController(
        address=os.getenv('BLUETOOTH_ADDRESS', 'E5:D7:EE:F7:7E:8E'),
        light_char="932c32bd-0002-47a2-835a-a8d455b859dd",
        brightness_char="932c32bd-0003-47a2-835a-a8d455b859dd",
        temperature_char="932c32bd-0004-47a2-835a-a8d455b859dd",
        color_char="932c32bd-0005-47a2-835a-a8d455b859dd"
    )

    @app.route('/')
    async def main():
        return render_template('index.html')

    @app.route('/connect')
    async def run_connect():
        success = await controller.connect()
        return redirect(url_for('main'))

    @app.route('/off')
    async def run_off():
        await controller.turn_off()
        return redirect(url_for('main'))

    @app.route('/on')
    async def run_on():
        await controller.turn_on()
        return redirect(url_for('main'))

    @app.route('/color')
    async def run_color():
        rgb = request.args.get('rgb', '').split(',')
        try:
            rgb = [int(x) for x in rgb]
            await controller.put_color(rgb[0], rgb[1], rgb[2])
        except (ValueError, IndexError):
            logger.error("Couleur RGB invalide")
        return redirect(url_for('main'))

    @app.route('/brightness')
    async def run_brightness():
        try:
            bright = int(request.args.get('p', 50))
            await controller.put_brightness(bright)
        except ValueError:
            logger.error("Luminosité invalide")
        return redirect(url_for('main'))

    return app

if __name__ == "__main__":
    app = create_app()
    app.run(host=os.getenv('APP_HOST', '192.168.0.11'), debug=True)