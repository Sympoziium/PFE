# Notes de migration — Pi Zero W (V1) → Pi Zero 2W (V2)

> **Statut :** En cours  
> **Objectif :** Migrer l'environnement du robot Zumi du Raspberry Pi Zero W (ARM11, 32-bit, monocœur) vers le Raspberry Pi Zero 2W (Cortex-A53, 64-bit, quad-core) avec Raspberry Pi OS Bookworm Lite 64-bit et Python 3.11.

---

## 1. Contexte

Le passage du V1 au V2 n'est pas un simple swap de carte SD. L'image OS du Zumi (fournie par Robolink) est construite spécifiquement pour le Pi Zero W V1 et n'est pas compatible avec le V2. La stratégie retenue est donc une installation propre sur image fraîche, suivie d'une réinstallation manuelle de toutes les dépendances.

Robolink confirme officiellement que le Pi Zero 2W n'est pas supporté *out of the box* :
> *"Every Pi is different and our Zumi software was built to run specifically on the Pi Zero W only."* — Forum Robolink
https://forum.robolink.com/category/14/zumi
---

## 2. Environnement cible

| Paramètre | Valeur |
|---|---|
| Matériel | Raspberry Pi Zero 2W |
| OS | Raspberry Pi OS Lite **64-bit** (Bookworm) |
| Python | 3.11.2 |
| pip | 26.0.1 (dans venv) |
| Environnement Python | `~/venv` (venv avec `--system-site-packages`) |

---

## 3. Diagnostic des dépendances du SDK Zumi

### 3.1 Méthodologie

L'analyse a été conduite directement sur le Pi V1 (encore fonctionnel) en inspectant le code source de la librairie installée sous Python 3.5 :

```bash
# Inspecter le core de la lib
cat /usr/local/lib/python3.5/dist-packages/zumi/zumi.py | head -50

# Lister tous les sous-modules
ls /usr/local/lib/python3.5/dist-packages/zumi/
ls /usr/local/lib/python3.5/dist-packages/zumi/util/

# Inspecter protocol.py
cat /usr/local/lib/python3.5/dist-packages/zumi/protocol.py

# Inspecter les imports de tous les utilitaires
head -20 /usr/local/lib/python3.5/dist-packages/zumi/util/*.py
```

### 3.2 Dépendances identifiées — zumi.py (core)

Les imports au niveau global de `zumi.py` sont :

```python
import smbus2
import RPi.GPIO as GPIO
import numpy as np
# + stdlib uniquement (os, time, math, logging, etc.)
```

`picamera` est **absente** des imports globaux. Elle n'apparaît que dans `preboot_to_postboot()` via un import local (`from zumi.util.screen import Screen`), donc elle ne bloque pas l'import de base.

### 3.3 Dépendances identifiées — protocol.py

Contient uniquement des définitions de constantes et d'énumérations (classes `Accelerometer`, `Gyro`, `MPURegister`, `Command`, etc.). **Aucune dépendance externe.** Compatible sans modification.

### 3.4 Dépendances identifiées — util/ (sous-modules)

| Fichier | Dépendances problématiques | Utilisé par notre projet | Action |
|---|---|---|---|
| `util/camera.py` | `picamera`, `IPython`, `PIL` | ❌ Non — remplacé par `picam2.py` | Ignorer |
| `util/screen.py` | `Adafruit_SSD1306` | ✅ Oui — bootstrap OLED | **Patch requis** (voir section 5) |
| `util/vision.py` | `pyzbar`, `cv2` | ❌ Non — remplacé par nos détecteurs | Ignorer |
| `util/maze.py` | `Adafruit_SSD1306` | ❌ Non | Ignorer |
| `util/color_classifier.py` | `cv2`, `numpy` | ❌ Non | Ignorer |
| `util/gyro_draw.py` | `PIL` | ❌ Non | Ignorer |
| `util/line_tracer.py` | Aucune externe | ❌ Non | Ignorer |
| `util/tourist_demo_helper.py` | `camera.py` → `picamera` | ❌ Non | Ignorer |
| `protocol.py` | Aucune | ✅ Oui | ✅ Rien à faire |

---

## 4. Tableau des conflits et résolutions

| Dépendance | Version V1 | Problème sur Bookworm/Python 3.11 | Sévérité | Solution retenue |
|---|---|---|---|---|
| `smbus2` | 0.3.0 | Aucun — installable via pip | ✅ Aucune | `pip install smbus2` |
| `pyzbar` | inconnu | Aucun — installable via pip | ✅ Aucune | `pip install pyzbar` |
| `numpy` | 1.16.3 | Version plus récente disponible, rétrocompatible | ✅ Aucune | `sudo apt install python3-numpy` |
| `RPi.GPIO` | 0.6.5 | Dépréciée sur Bookworm — remplacée par `lgpio` | ⚠️ Modérée | Shim `rpi-lgpio` (émule l'API RPi.GPIO) |
| `pigpio` | 1.38 | Installable, mais requiert le daemon `pigpiod` | ⚠️ Modérée | `pip install pigpio` + configurer `pigpiod` |
| `picamera` | 1.13 | **Abandonnée sur Bookworm** — legacy camera stack retiré | ❌ Critique | Ignorée (notre projet utilise déjà `picamera2`) |
| `Adafruit_SSD1306` | inconnu | Non maintenue, incompatible Python 3.11 | ❌ Critique | Remplacement par `luma.oled` (voir section 5) |

---

## 5. Plan d'installation — Pi Zero 2W

Exécuter dans l'ordre suivant.

### Étape 0 — Backup de l'image du Pi original (V1)
avant de faire quoi que ce soit, il est recommandé de faire une sauvegarde complète de l'image SD du Pi V1. Cela permet de revenir en arrière en cas de problème et de conserver une copie fonctionnelle du système original.

pour ce faire on a besoin d'un lecteur de carte SD et d'un outil de clonage tird party (Py imager ne fait pas la copie)

***Outils recommandés :**
https://win32diskimager.org 

**Utilisation :**
dans win32 il sufit de naviguer jusqu'au dossier de destination de notre image dans "image file", de sélectionner notre lecteur de carte SD dans "device" puis de cliquer sur "read" pour faire la copie de l'image du V1 vers notre PC.

that's it! on a maintenant une sauvegarde de l'image du V1 sur notre PC au cas ou on aurait besoin d'y revenir.

### Étape 1 — Activer I2C

```bash
sudo raspi-config nonint do_i2c 0
# Vérifier que /dev/i2c-1 est présent
ls /dev/i2c*
```

### Étape 2 — Dépendances système via apt

```bash
sudo apt install -y python3-picamera2 python3-numpy python3-smbus2 i2c-tools libzbar0 libcamera-dev
```

### Étape 3 — Dépendances pip dans le venv

```bash
source ~/venv/bin/activate
pip install rpi-lgpio smbus2 pyzbar pigpio pyserial opencv-python flask
```

#### Étape 3.5 — Validation des dépendances 

```bash
# Vérifier que le venv est actif
echo $VIRTUAL_ENV

# Valider toutes les dépendances pip installées
pip list | grep -iE "opencv|rpi|lgpio|smbus|pyzbar|pigpio|pyserial|flask|numpy|opencv-python|flask"

# Valider les paquets apt
dpkg -l | grep -iE "python3-picamera2|python3-numpy|python3-smbus2|i2c-tools libzbar0 libcamera-dev"
```

### Étape 4 — Installation de Zumi

```bash
pip install zumi
```

### Étape 5 — Test d'import critique

```bash
python3 -c "from zumi.zumi import Zumi; print('Import Zumi OK')"
```

### Étape 6 — Validation des adresses i2c
comme le Pi communique directement avec le zumiboard via i2c, on doit s'assurer que les adresses sont les mêmes que sur le V1. pour cela on peut utiliser la commande `i2cdetect` pour scanner le bus i2c et vérifier que les périphériques sont détectés aux bonnes adresses.

#### Étape 6.1 — Scanner le bus i2c

**Config Original (V1)**
```bash

pi@zumi4585:~ $ sudo i2cdetect -y 1
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:          -- 04 -- -- -- -- -- -- -- -- 0d -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- 3c -- -- --
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- 68 -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --
```
#### Étape 6.2 — Inspection du SDK et de l'appartenance des adresses

Trace d'appartenance des adresses i2c :

```bash

pi@zumi4585:~ $ # Sur le Pi V1
pi@zumi4585:~ $ grep -r "0x3C\|0x68\|0x04\|0x0D" /usr/local/lib/python3.5/dist-packages/zumi/
/usr/local/lib/python3.5/dist-packages/zumi/protocol.py:    Arduino = 0x04
/usr/local/lib/python3.5/dist-packages/zumi/protocol.py:    MPU = 0x68
/usr/local/lib/python3.5/dist-packages/zumi/util/screen.py:        self.SSD1306_I2C_ADDRESS = 0x3C  # 011110+SA0+RW - 0x3C or 0x3D
/usr/local/lib/python3.5/dist-packages/zumi/zumi.py:    arduino_address = 0x04
/usr/local/lib/python3.5/dist-packages/zumi/zumi.py:        self.REG_ZOUT_LSB = 0x04
/usr/local/lib/python3.5/dist-packages/zumi/zumi.py:        bus.write_byte(0x04, 0b00000000)
/usr/local/lib/python3.5/dist-packages/zumi/zumi.py:                if device == 0x68:
/usr/local/lib/python3.5/dist-packages/zumi/zumi.py:                self.bus.write_byte(0x04, 0b11000000)
pi@zumi4585:~ $

```
#### Étape 6.3 — Validation par registre des adresses manquantes

```bash

pi@zumi4585:~ $ sudo i2cget -y 1 0x0D 0x0D
0xff   # Registre Chip ID → 0xFF (valeur constructeur documentée)
```

**Conclusion** :
- 0x04 → Arduino (communication i2c avec le zumiboard)
- 0x68 → MPU (accéléromètre/gyroscope)
- 0x3C → OLED (écran i2c)
- 0x0D → QMC5883L (magnétomètre) http://wiki.sunfounder.cc/images/7/72/QMC5883L-Datasheet-1.0.pdf 



### Étape 7 — VTest implantation nouveau Pi Zero 2W
on a fait le changement de branchement des 2 pi et on procède au test i2c pour valider que les périphériques sont détectés correctement sur le nouveau Pi Zero 2W.

**Config V2 (après installation)**
```bash

(venv) pi@pi:~ $ sudo i2cdetect -y 1
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- 0d -- --
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
30: -- -- -- -- -- -- -- -- -- -- -- -- 3c -- -- --
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- --
60: -- -- -- -- -- -- -- -- 68 -- -- -- -- -- -- --
70: -- -- -- -- -- -- -- --

```
---

# PROBLÈME IMPORTANT IDENTIFIER :
Lorsque je tente d'allumer le robot avec le nouveau Pi Zero 2W, il y a un flash des LED du zumiboard mais ensuite plus rien ne se passe. le robot ne boot pas et n'est pas détecté en SSH. Le problème vient de l'allimentation original, le zumi V1 consommais beaucoup moins que son homologue V2, comme la demande en courant du V2 est plus élevée la batterie ne parvient pas a fournir l'allimentation nécessaire pour booter. Pour y parvenir, il faut passer par l'alimentation par USB (en branchant le Pi Zero 2W directement a un chargeur USB).

Il est donc possible d'alimenter le Pi et bord de cette façon, mais ça ne règle pas le problème, l'écran OLED affiche un chargement puis au bout de celui-ci il affiche l'écran d'erreur "Zumi can't wake up". j'ai l'impression que les 2 alimentation entrent en conflit et cause un problême de communication i2c, cependant ce qui me laice perplex ces que même sans activer la batterie (donc si on passe seulement par l'allimentation du Pi), les adresse des périphériques 68, 3c et 0d sont toujours visible ce qui indique que le Pi fourni le zumibord en courant puisque ceux-ci passent par un bus commun. (**vrais source du problème**) cela pourrais indiquer qu'il s'agisrais plus tôt d'une procédure handshake entre le Pi et le Atmega du zumibord qui n'est pas conclu.

## Voir section 8 pour le diagnostic et la solution de ce problème. 

---

## 6. Patch screen.py — Remplacement de Adafruit_SSD1306

> **Priorité :** À faire après validation du core Zumi.  
> **Complexité estimée :** Faible — remplacement mécanique (~25 occurrences).

### Contexte

`Adafruit_SSD1306` est une librairie abandonnée incompatible avec Python 3.11. Le remplacement moderne officiel est `luma.oled`, dont l'API est quasi-identique pour les opérations de base.

La stratégie retenue est de **sortir `screen.py` du SDK Zumi** et de le versionner dans notre projet sous `core/hardware/screen.py`. Cela permet de le maintenir sous contrôle Git et de l'adapter sans modifier le SDK.

Ne pas oublier de mettre à jour les imports dans notre code pour pointer vers `core.hardware.screen` plutôt que `zumi.util.screen`.

### 6.1 Installation de luma.oled

```bash
sudo apt install -y python3-dev libfreetype6-dev libjpeg-dev build-essential
pip install luma.oled
```

### 6.2 Récupérer screen.py depuis le V1

```bash
# Sur le Pi V1
cat /usr/local/lib/python3.5/dist-packages/zumi/util/screen.py
```

Copier le contenu dans `core/hardware/screen.py` du repo.

### 6.3 Modifier l'initialisation

**Avant :**
```python
import Adafruit_SSD1306

self.disp = Adafruit_SSD1306.SSD1306_128_64(rst=self.RST)
self.disp.begin()
```

**Après :**
```python
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306

serial = i2c(port=1, address=0x3C)
self.disp = ssd1306(serial)
# begin() supprimé — géré automatiquement par luma
```

### 6.4 Remplacer les appels display()

Effectuer un remplacement sur les ~25 occurrences du pattern suivant dans `screen.py` :

**Avant :**
```python
self.disp.image(self.screen_image)
self.disp.display()
```

**Après :**
```python
self.disp.display(self.screen_image)
```

### 6.5 Supprimer les appels obsolètes

Supprimer tous les appels à `self.disp.begin()` et `self.disp.clear()` — ces opérations sont gérées automatiquement par luma.oled à l'initialisation.

---

## 7. Notes additionnelles

- **OpenCV** : sur le V1, OpenCV était installé exclusivement via pip (`opencv-python 4.4.0.42`, confirmé par diagnostic). Sur le V2, on conserve la même approche — installation via pip dans le venv. `opencv-python` doit figurer dans l'étape 3 (pip) et **non** dans l'étape apt.
- **venv** : toujours activer l'environnement virtuel avant toute installation pip (`source ~/venv/bin/activate`). Voir Annexe A pour l'activation automatique au démarrage SSH.
- **Environnement PEP 668** : Bookworm bloque l'installation pip système par défaut. Toujours travailler dans le venv.

---

## 8. Problème identifié — Séquence de démarrage (handshake Pi ↔ ATmega)

### 8.1 Symptôme

Au premier démarrage avec le Pi Zero 2W, le Zumi board affiche la séquence
d'initialisation normale (splash screen + barre de chargement), puis affiche
l'erreur **"Zumi can't wake up"** et reste bloqué.

### 8.2 Diagnostic

#### 8.2.1 Services systemd sur le Pi V1

Inspection des services activés sur l'image originale Robolink :

```bash
systemctl list-unit-files --state=enabled
systemctl list-unit-files | grep -i zumi
```

Résultat — services pertinents identifiés :

| Service | État | Rôle |
|---|---|---|
| `postbootup.service` | enabled | **Handshake Pi ↔ ATmega** |
| `zumidashboard.service` | enabled | Interface web Zumi |
| `zumi_updater.service` | disabled | Mise à jour OTA |
| `zumi_wifi_setup.service` | disabled | Configuration WiFi initiale |

#### 8.2.2 Inspection de postbootup.service

```bash
systemctl cat postbootup.service
```

```
ExecStart=/usr/bin/python3 -c 'from zumi.zumi import preboot_to_postboot; preboot_to_postboot()'
```

Le service appelle `preboot_to_postboot()` du SDK Zumi. Sans ce service,
le ATmega ne reçoit jamais le signal de confirmation du Pi et reste en attente.

#### 8.2.3 Analyse de preboot_to_postboot()

```bash
grep -A 30 "def preboot_to_postboot" /usr/local/lib/python3.5/dist-packages/zumi/zumi.py
```

Séquence identifiée :
1. Attente que le ATmega drive **GPIO 4 à LOW** (signal de disponibilité)
2. Envoi du byte `0b11000000` à l'adresse I2C `0x04` (handshake)
3. Appel cosmétique à `Screen().draw_image_by_name('wakingup_witheyes')` — sans impact fonctionnel

#### 8.2.4 Validation du GPIO 4 sur Pi Zero 2W

Le shim `rpi-lgpio` (remplaçant de `RPi.GPIO` sur Bookworm) a été validé
expérimentalement sur le Pi Zero 2W :

```bash
python3 -c "
import RPi.GPIO as GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(4, GPIO.IN)
print('GPIO 4 state:', GPIO.input(4))
GPIO.cleanup()
"
```

| État du Zumi board | Valeur GPIO 4 | Interprétation |
|---|---|---|
| Switch OFF (non alimenté) | `1` (HIGH) | ATmega non prêt |
| Switch ON (alimenté) | `0` (LOW) | ATmega prêt → envoyer handshake |

### 8.3 Cause racine

Le service `postbootup.service` de l'image Robolink n'existe pas sur l'image
Bookworm propre. Le ATmega attend indéfiniment le handshake du Pi, ce qui
provoque l'erreur "Zumi can't wake up".

### 8.4 Solution retenue

Deux livrables créés et versionnés dans le projet :

**`core/hardware/boot.py`** — Patch de compatibilité de `preboot_to_postboot()` :
- Suppression de l'import `zumi.util.screen` (incompatible Python 3.11)
- Suppression de l'appel cosmétique `Screen().draw_image_by_name()`
- Ajout d'un timeout de 30 secondes sur la boucle GPIO (sécurité)
- Ajout de logging pour faciliter le débogage

**`postbootup.service`** — Service systemd à déployer sur le Pi Zero 2W :

```bash
# Déploiement sur le Pi Zero 2W
sudo cp /home/pi/PFE/core/hardware/postbootup.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable postbootup.service
sudo systemctl start postbootup.service

# Validation
sudo systemctl status postbootup.service
```

### 8.5 Note sur l'alimentation

La batterie originale du Zumi (dimensionnée pour le Pi Zero W V1, ~120 mA)
ne fournit pas suffisamment de courant pour démarrer le Pi Zero 2W (~350 mA).

**Contournement validé :** alimenter le Pi Zero 2W via USB externe, puis
allumer le switch du Zumi board. Les deux alimentations coexistent sans conflit.

**Impact projet :** cette contrainte devra être adressée pour le déploiement
final (remplacement de la batterie ou régulateur de tension adapté).

---

## Annexe A — Activation automatique du venv à la connexion SSH

### Contexte

En développement actif, on souhaite que le venv soit déjà actif dès qu'on se connecte en SSH, afin de pouvoir lancer `python main.py` immédiatement sans conflit d'imports. Le programme est lancé **manuellement** — cette annexe ne couvre pas le démarrage automatique de `main.py`.

### Procédure

Ajouter la ligne d'activation à la fin de `~/.bashrc` :

```bash
echo "source ~/venv/bin/activate" >> ~/.bashrc
```

Ou manuellement :

```bash
nano ~/.bashrc
# Ajouter à la fin du fichier :
source ~/venv/bin/activate
```

Appliquer immédiatement sans redémarrer :

```bash
source ~/.bashrc
```

### Résultat attendu

À chaque nouvelle connexion SSH, le prompt affichera automatiquement le préfixe `(venv)` :

```
(venv) pi@pi:~ $
```

Tous les imports Python utiliseront alors les packages installés dans le venv sans aucune action manuelle supplémentaire.

### Note

Cette configuration s'applique uniquement aux **sessions SSH interactives**. Elle n'affecte pas les scripts lancés par `systemd` ou `cron`, qui doivent pointer explicitement vers `/home/pi/venv/bin/python` si nécessaire.

---

*Dernière mise à jour : migration en cours — validation core Zumi en attente.*
