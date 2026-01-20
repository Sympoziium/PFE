# Programme de test des fonctionnalités de vision sur raspberry pi



from picamera2 import Picamera2
import time




picam.capture_file("test.jpg") # Capture d'une image et sauvegarde dans un fichier


class Vision:
    def __init__(self, resolution=(640, 480)):
        self.resolution = resolution
        self.camera = self.initialize_camera()

    def initialize_camera(self):
        print(f"Initializing camera with resolution {self.resolution}")
        # Déclaration de l'objet caméra
        picam = Picamera2()

        # configuration de la caméra
        cam_config = picam.create_preview_configuration(main={"size": (self.resolution[0], self.resolution[1])}) # Configuration de la résolution
        picam.configure(cam_config)

        return picam

    def capture_frame(self):
        # Placeholder for frame capture logic
        print("Capturing frame from camera")

        # Démarrage de la caméra
        self.camera.start_preview(Preview.QTGL) # Affichage de l'aperçu dans une fenêtre QT
        self.camera.start() # Démarrage de la capture vidéo
        time.sleep(2) # Attente de 2 secondes pour que la caméra s'initialise correctement

        self.camera.capture_file("test.jpg") # Capture d'une image et sauvegarde dans un fichier

        return "FrameData"

    def process_frame(self, frame):
        # Placeholder for frame processing logic
        print("Processing frame")
        return "ProcessedFrameData"

    def release_camera(self):
        # Placeholder for camera release logic
        print("Releasing camera resources")


# === LANCEMENT DU PROGRAMME === 
if __name__ == '__main__': 
    # --- NOUVEAU : Démarrer le thread watchdog --- 
    
    # ------------------------------------------ 
     
    print("Programme is running") # Vous pouvez garder votre print 
    vision_system = Vision(resolution=(800, 600))