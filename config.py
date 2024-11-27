import configparser
import os

def create_default_config():
    config = configparser.ConfigParser()

    # Bluetooth configuration must exist
    config['BLUETOOTH'] = {
        'address': '00:00:00:00:00:00'
    }

    # Create the config file if it doesn't exist
    if not os.path.exists('modes.config'):
        with open('modes.config', 'w') as configfile:
            config.write(configfile)

def set_mode_config(profile_name: str, state: dict):
    """
    Enregistre un mode avec l'état complet de la lampe.
    
    :param profile_name: Nom du profil à sauvegarder
    :param state: Dict contenant l'état complet {light_state, brightness, color}
    """
    config = configparser.ConfigParser()
    config.read('modes.config')
    
    if profile_name not in config:
        config[profile_name] = {}
    
    # Sauvegarde de tous les paramètres d'état
    if state.get('light_state') is not None:
        config[profile_name]['light_state'] = str(state['light_state'])
    if state.get('brightness') is not None:
        config[profile_name]['brightness'] = str(state['brightness'])
    if state.get('color') is not None:
        config[profile_name]['color'] = str(state['color'])
    
    with open('modes.config', 'w') as configfile:
        config.write(configfile)

if __name__ == '__main__':
    create_default_config()