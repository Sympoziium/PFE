#!/usr/bin/env python
# -*- coding: utf-8 -*-
# boot.py
# ------------------
"""
core/hardware/boot.py

Patch de compatibilité — Séquence de démarrage Zumi pour Pi Zero 2W / Bookworm 64-bit.

Origine : zumi.zumi.preboot_to_postboot() du SDK Zumi (Robolink)
Raison du patch :
    1. La fonction originale importe zumi.util.screen (Adafruit_SSD1306),
       incompatible avec Python 3.11 / Bookworm.
    2. L'appel à Screen().draw_image_by_name('wakingup_witheyes') est purement
       cosmétique et n'a aucun rôle dans le handshake Pi ↔ ATmega.
    3. Un timeout a été ajouté sur la boucle GPIO pour éviter un blocage
       infini en cas de défaillance matérielle.

Séquence de démarrage validée (Pi Zero W V1 → Pi Zero 2W V2) :
    1. Attendre que le ATmega (Zumi board) drive GPIO 4 à LOW
       → signal que le ATmega est initialisé et prêt
    2. Envoyer le byte 0b11000000 à l'adresse I2C 0x04 (ATmega)
       → handshake confirmant que le Pi est opérationnel
    3. Le ATmega quitte son écran d'attente "Zumi can't wake up"

Références :
    - SDK Zumi source : zumi/zumi.py (Pi Zero W V1, Python 3.5)
    - Adresses I2C validées par i2cdetect sur matériel réel (V1 et V2)
    - GPIO 4 validé par test direct sur Pi Zero 2W avec rpi-lgpio.
"""

import time
import logging
import smbus2
import RPi.GPIO as GPIO

logger = logging.getLogger(__name__)

# Adresse I2C du microcontrôleur ATmega sur le Zumi board
# Validée par inspection du SDK (protocol.py : Arduino = 0x04)
# et confirmée par i2cdetect sur matériel réel
ARDUINO_I2C_ADDRESS = 0x04

# GPIO 4 : signal de synchronisation ATmega → Pi
# LOW = ATmega prêt à recevoir le handshake
BOOT_SYNC_PIN = 4

# Timeout maximal d'attente du signal ATmega (secondes)
# Évite un blocage infini si le Zumi board n'est pas alimenté
BOOT_TIMEOUT_SECONDS = 30


def preboot_to_postboot():
    """
    Exécute la séquence de handshake entre le Pi et le ATmega du Zumi board.

    Cette fonction doit être appelée au démarrage du Pi, via le service
    systemd postbootup.service, avant tout autre accès au SDK Zumi.

    Raises:
        TimeoutError: Si le ATmega ne signale pas sa disponibilité dans
                      le délai imparti (BOOT_TIMEOUT_SECONDS).
        IOError: Si la communication I2C avec le ATmega échoue.
    """
    bus = smbus2.SMBus(1)

    GPIO.setmode(GPIO.BCM)
    GPIO.setup(BOOT_SYNC_PIN, GPIO.IN)

    logger.info("Attente du signal de synchronisation ATmega (GPIO %d)...", BOOT_SYNC_PIN)

    # Attendre que le ATmega drive GPIO 4 à LOW
    # Validé expérimentalement : HIGH = ATmega non prêt, LOW = ATmega prêt
    elapsed = 0.0
    while GPIO.input(BOOT_SYNC_PIN) == 1:
        time.sleep(0.01)
        elapsed += 0.01
        if elapsed >= BOOT_TIMEOUT_SECONDS:
            GPIO.cleanup()
            bus.close()
            raise TimeoutError(
                f"ATmega non détecté après {BOOT_TIMEOUT_SECONDS}s. "
                "Vérifier l'alimentation du Zumi board."
            )

    time.sleep(1)

    # Handshake : signaler au ATmega que le Pi est opérationnel
    # Byte 0b11000000 = valeur attendue par le firmware ATmega du Zumi board
    logger.info("Envoi du handshake au ATmega (0x%02X)...", ARDUINO_I2C_ADDRESS)
    try:
        bus.write_byte(ARDUINO_I2C_ADDRESS, 0b11000000)
    except IOError:
        # Retry unique — comportement reproduit depuis le SDK original
        time.sleep(0.01)
        bus.write_byte(ARDUINO_I2C_ADDRESS, 0b11000000)

    logger.info("Handshake complété. Zumi board opérationnel.")

    GPIO.cleanup()
    bus.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    preboot_to_postboot()
