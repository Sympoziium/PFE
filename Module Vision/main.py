# main.py
# Programme de test des fonctionnalités de la caméra PiCam2

from camera.picam2 import PiCam2
import cv2
import time


def main():
    camera = PiCam2()
    camera.start()
    time.sleep(2)  # Allow camera to warm up

    test_input = ''

    while test_input.lower() != 'esc':
        
        test_input = input("Press ESC to stop or space to capture frames...\n")
        if test_input == ' ':
            frame = camera.get_frame()
            print("Captured frame of shape:", frame.shape)
            
            filename = f"frame_{int(time.time())}.jpg" # on formate l'heure pour permettre d'enregistrer plusieurs images sans écraser les précédentes
            cv2.imwrite(filename, frame)
            print(f"Frame saved as {filename}")

        time.sleep(2) # délais de 2 secondes entre chaque capture

    camera.stop()