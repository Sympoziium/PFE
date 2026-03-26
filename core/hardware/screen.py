"""
core/hardware/screen.py

Patch de compatibilité — Écran OLED SSD1306 pour Pi Zero 2W / Bookworm 64-bit.

Origine : zumi.util.screen (SDK Zumi, Robolink, Python 3.5)
Raison du patch :
    Adafruit_SSD1306 est une librairie abandonnée, incompatible avec Python 3.11.
    Le remplacement retenu est luma.oled, dont l'API de rendu (display(image)) est
    compatible avec les images PIL en mode '1' utilisées dans la classe originale.

Stratégie de migration :
    - self.disp (Adafruit_SSD1306) → self.disp (luma.oled ssd1306)
    - Rendu image : self.disp.image(img) + self.disp.display()
                   → self.disp.display(img)   [API luma.oled]
    - Commandes bas-niveau (scroll, on/off, contrast) : routées directement
      via smbus2, en utilisant les constantes SSD1306 déjà présentes dans la classe.
      luma.oled n'expose pas ces commandes de scroll dans son API publique.
    - self.disp.clear() + self.disp.begin() : supprimés — gérés automatiquement
      par luma.oled à l'initialisation.
    - self.disp.set_contrast() : remplacé par appel smbus2 direct.

Adresse I2C validée par i2cdetect sur matériel réel (Pi Zero W V1 et Pi Zero 2W V2) :
    SSD1306 → 0x3C
    Confirmée par SDK source : screen.py → self.SSD1306_I2C_ADDRESS = 0x3C

Dépendance :
    pip install luma.oled
    sudo apt install -y python3-dev libfreetype6-dev libjpeg-dev build-essential
"""

import time
import os
import math
import smbus2
from PIL import Image, ImageFont, ImageDraw
from luma.core.interface.serial import i2c
from luma.oled.device import ssd1306


class Screen:
    # Raspberry Pi pin configuration (conservé pour compatibilité)
    RST = 24
    EYE_IMAGE_FOLDER_PATH = os.path.dirname(os.path.abspath(__file__)) + '/images/'
    TEXT_FILE_PATH = os.path.dirname(os.path.abspath(__file__)) + "/futura.ttf"
    EXCITED = {"excited1", "excited2", "excited3"}

    def __init__(self, clear=True):
        # Constantes de registres SSD1306 — conservées pour les commandes bas-niveau
        self.SSD1306_I2C_ADDRESS = 0x3C
        self.SSD1306_SETCONTRAST = 0x81
        self.SSD1306_DISPLAYALLON_RESUME = 0xA4
        self.SSD1306_DISPLAYALLON = 0xA5
        self.SSD1306_NORMALDISPLAY = 0xA6
        self.SSD1306_INVERTDISPLAY = 0xA7
        self.SSD1306_DISPLAYOFF = 0xAE
        self.SSD1306_DISPLAYON = 0xAF
        self.SSD1306_SETDISPLAYOFFSET = 0xD3
        self.SSD1306_SETCOMPINS = 0xDA
        self.SSD1306_SETVCOMDETECT = 0xDB
        self.SSD1306_SETDISPLAYCLOCKDIV = 0xD5
        self.SSD1306_SETPRECHARGE = 0xD9
        self.SSD1306_SETMULTIPLEX = 0xA8
        self.SSD1306_SETLOWCOLUMN = 0x00
        self.SSD1306_SETHIGHCOLUMN = 0x10
        self.SSD1306_SETSTARTLINE = 0x40
        self.SSD1306_MEMORYMODE = 0x20
        self.SSD1306_COLUMNADDR = 0x21
        self.SSD1306_PAGEADDR = 0x22
        self.SSD1306_COMSCANINC = 0xC0
        self.SSD1306_COMSCANDEC = 0xC8
        self.SSD1306_SEGREMAP = 0xA0
        self.SSD1306_CHARGEPUMP = 0x8D
        self.SSD1306_EXTERNALVCC = 0x1
        self.SSD1306_SWITCHCAPVCC = 0x2
        self.SSD1306_ACTIVATE_SCROLL = 0x2F
        self.SSD1306_DEACTIVATE_SCROLL = 0x2E
        self.SSD1306_SET_VERTICAL_SCROLL_AREA = 0xA3
        self.SSD1306_RIGHT_HORIZONTAL_SCROLL = 0x26
        self.SSD1306_LEFT_HORIZONTAL_SCROLL = 0x27
        self.SSD1306_VERTICAL_AND_RIGHT_HORIZONTAL_SCROLL = 0x29
        self.SSD1306_VERTICAL_AND_LEFT_HORIZONTAL_SCROLL = 0x2A

        try:
            # Bus smbus2 — conservé pour les commandes bas-niveau (scroll, on/off)
            self.bus = smbus2.SMBus(1)

            # PATCH : remplacement de Adafruit_SSD1306 par luma.oled
            # luma.oled gère automatiquement l'initialisation et le begin()
            serial = i2c(port=1, address=self.SSD1306_I2C_ADDRESS)
            self.disp = ssd1306(serial)

            self.width = self.disp.width    # 128
            self.height = self.disp.height  # 64

            self._vccstate = None
            self._pages = self.height // 8
            self._buffer = [0] * (self.width * self._pages)

            self.screen_image = Image.new('1', (self.width, self.height))
            self.draw = ImageDraw.Draw(self.screen_image)
            self.stop_scroll()
            # PATCH : clear() et display() initiaux gérés par luma.oled —
            # on affiche simplement l'image noire initiale
            if clear:
                self.disp.display(self.screen_image)
        except Exception:
            print("OLED screen is not connected")

    def command(self, value):
        """Envoie un byte de commande à l'écran via smbus2."""
        control = 0x00  # Co = 0, DC = 0
        value = value & 0xff
        self.bus.write_byte_data(self.SSD1306_I2C_ADDRESS, control, value)

    def begin(self):
        """Initialise l'écran (conservé pour compatibilité API)."""
        self._vccstate = self.SSD1306_SWITCHCAPVCC
        self._initialize()
        self.command(self.SSD1306_DISPLAYON)

    def _initialize(self):
        """Séquence d'initialisation bas-niveau SSD1306."""
        self.command(self.SSD1306_DISPLAYOFF)
        self.command(self.SSD1306_SETDISPLAYCLOCKDIV)
        self.command(0x80)
        self.command(self.SSD1306_SETMULTIPLEX)
        self.command(0x3F)
        self.command(self.SSD1306_SETDISPLAYOFFSET)
        self.command(0x0)
        self.command(self.SSD1306_SETSTARTLINE | 0x0)
        self.command(self.SSD1306_CHARGEPUMP)
        if self._vccstate == self.SSD1306_EXTERNALVCC:
            self.command(0x10)
        else:
            self.command(0x14)
        self.command(self.SSD1306_MEMORYMODE)
        self.command(0x00)
        self.command(self.SSD1306_SEGREMAP | 0x1)
        self.command(self.SSD1306_COMSCANDEC)
        self.command(self.SSD1306_SETCOMPINS)
        self.command(0x12)
        self.command(self.SSD1306_SETCONTRAST)
        if self._vccstate == self.SSD1306_EXTERNALVCC:
            self.command(0x9F)
        else:
            self.command(0xCF)
        self.command(self.SSD1306_SETPRECHARGE)
        if self._vccstate == self.SSD1306_EXTERNALVCC:
            self.command(0x22)
        else:
            self.command(0xF1)
        self.command(self.SSD1306_SETVCOMDETECT)
        self.command(0x40)
        self.command(self.SSD1306_DISPLAYALLON_RESUME)
        self.command(self.SSD1306_NORMALDISPLAY)

    def display(self):
        """Écrit le buffer interne sur l'écran physique via smbus2."""
        self.command(self.SSD1306_COLUMNADDR)
        self.command(0)
        self.command(self.width - 1)
        self.command(self.SSD1306_PAGEADDR)
        self.command(0)
        self.command(self._pages - 1)
        for i in range(0, len(self._buffer), 16):
            control = 0x40
            self.bus.write_i2c_block_data(self.SSD1306_I2C_ADDRESS, control, self._buffer[i:i + 16])

    def image(self, image):
        """Convertit une image PIL en buffer interne."""
        if image.mode != '1':
            raise ValueError('Image must be in mode 1.')
        imwidth, imheight = image.size
        if imwidth != self.width or imheight != self.height:
            raise ValueError('Image must be same dimensions as display ({0}x{1}).'.format(self.width, self.height))
        pix = image.load()
        index = 0
        for page in range(self._pages):
            for x in range(self.width):
                bits = 0
                for bit in [0, 1, 2, 3, 4, 5, 6, 7]:
                    bits = bits << 1
                    bits |= 0 if pix[(x, page * 8 + 7 - bit)] == 0 else 1
                self._buffer[index] = bits
                index += 1

    def clear(self):
        """Efface le buffer interne."""
        self._buffer = [0] * (self.width * self._pages)

    # -------------------------------------------------------------------------
    # Méthodes de dessin — PATCH : self.disp.image(x) + self.disp.display()
    #                              → self.disp.display(x)
    # -------------------------------------------------------------------------

    def draw_rect(self, x, y, width, height, thickness=1, fill_in=0):
        self.draw.rectangle((x, y, x + width, y + height), outline=thickness, fill=fill_in)
        self.disp.display(self.screen_image)

    def draw_square(self, x, y, width, thickness=1, fill_in=0):
        self.draw.rectangle((x, y, x + width, y + width), outline=thickness, fill=fill_in)
        self.disp.display(self.screen_image)

    def draw_point(self, x, y, fill_in=1):
        self.draw.point((x, y), fill=fill_in)
        self.disp.display(self.screen_image)

    def draw_line(self, x1, y1, x2, y2, thickness=1, fill_in=1):
        self.draw.line(((x1, y1), (x2, y2)), width=thickness, fill=fill_in)
        self.disp.display(self.screen_image)

    def draw_polygon(self, points_list, fill_in=1):
        self.draw.polygon(points_list, fill=fill_in)
        self.disp.display(self.screen_image)

    def draw_triangle(self, x1, y1, x2, y2, x3, y3, fill_in=1):
        points_list = [(x1, y1), (x2, y2), (x3, y3)]
        self.draw.polygon(points_list, fill=fill_in)
        self.disp.display(self.screen_image)

    def draw_arc(self, x1, y1, x2, y2, start_ang, end_ang, fill_in=1):
        self.draw.arc([x1, y1, x2, y2], start_ang, end_ang, fill=fill_in)
        self.disp.display(self.screen_image)

    def draw_chord(self, x1, y1, x2, y2, start_ang, end_ang, fill_in=1):
        self.draw.chord([x1, y1, x2, y2], start_ang, end_ang, fill=fill_in)
        self.disp.display(self.screen_image)

    def draw_ellipse(self, x, y, width, height, fill_in=0):
        self.draw.ellipse((x, y, x + width, y + height), outline=1, fill=fill_in)
        self.disp.display(self.screen_image)

    def draw_circle(self, x, y, diameter, fill_in=0):
        self.draw.ellipse((x, y, x + diameter, y + diameter), outline=1, fill=fill_in)
        self.disp.display(self.screen_image)

    def print(self, *messages, x=0, y=0, fill_in=1, font_size=12):
        full_message = ""
        for message in messages:
            full_message = full_message + str(message)
        font = ImageFont.truetype(self.TEXT_FILE_PATH, font_size)
        self.draw.text((x, y), full_message, font=font, fill=fill_in)
        self.disp.display(self.screen_image)

    def draw_graph(self, x, y, y_offset=0, x_offset=0, scale=1, draw_axes=True):
        y_center = self.height / 2 - y_offset
        x_center = self.width / 2 + x_offset
        x_new = int((x_center + x) * scale)
        y_new = int((y_center - y) * scale)
        self.draw.point((x_new, y_new), fill=1)
        if draw_axes:
            self.draw.line(((0, y_center), (self.width, y_center)), width=1, fill=1)
            self.draw.line(((x_center, 0), (x_center, self.height)), width=1, fill=1)
        self.disp.display(self.screen_image)

    def loop_text(self, direction, string='', line=25, font_size=16):
        length = len(string)
        image = Image.new('1', (self.width, self.height))
        font = ImageFont.truetype(self.TEXT_FILE_PATH, font_size)
        draw = ImageDraw.Draw(image)
        size = draw.textsize(string, font=font)
        if 0 <= line <= 45:
            if size[0] > 128:
                print("The string entered is too long.")
            else:
                if direction == 'R':
                    self.stop_scroll()
                    draw.text((1, line), string, font=font, fill=255)
                    self.disp.display(image)
                    self.right_scroll()
                elif direction == 'L':
                    self.stop_scroll()
                    draw.text((1, line), string, font=font, fill=255)
                    self.disp.display(image)
                    self.left_scroll()
                elif direction == 'S':
                    self.stop_scroll()
        else:
            print('Lines can be entered from 0 to 45.')

    def clock(self, hour, minute, string='', font_size=18):
        image = Image.new('1', (self.width, self.height))
        font = ImageFont.truetype(self.TEXT_FILE_PATH, font_size)
        draw = ImageDraw.Draw(image)
        size = draw.textsize(string, font=font)
        width = self.width
        height = self.height
        draw.rectangle((0, 0, width, height), outline=0, fill=0)
        draw.ellipse((1, 1, 64, 64), outline=255, fill=0)
        draw.ellipse((6, 6, 58, 58), outline=255, fill=0)
        draw.ellipse((31, 31, 33, 33), outline=255, fill=0)
        timer_x = 32
        timer_y = height / 2
        basic_min_hand = 19
        amp_min_hand = 0.1
        min_hand = None
        hour_hand = None
        if minute <= 15:
            min_hand = basic_min_hand + (minute * amp_min_hand)
        elif minute <= 30:
            min_hand = basic_min_hand + ((15 - (minute - 15)) * amp_min_hand)
        elif minute <= 45:
            min_hand = basic_min_hand + ((minute - 30) * amp_min_hand)
        elif minute <= 60:
            min_hand = basic_min_hand + ((15 - (minute - 45)) * amp_min_hand)
        cla_minute = minute * 6 + 270
        if cla_minute > 360:
            cla_minute = cla_minute - 360
        rad_min = 3.14159 / 180 * cla_minute
        x = min_hand * math.cos(rad_min) + timer_x
        y = min_hand * math.sin(rad_min) + timer_y
        draw.line((timer_x, timer_y, x, y), fill=255)
        ampm_hour = hour
        if hour > 12:
            hour = hour - 12
        basic_hour_hand = 15
        amp_hour_hand = 0.1
        if hour <= 3:
            hour_hand = basic_hour_hand + (hour * amp_hour_hand)
        elif hour <= 6:
            hour_hand = basic_hour_hand + ((3 - (hour - 3)) * amp_hour_hand)
        elif hour <= 9:
            hour_hand = basic_hour_hand + ((hour - 6) * amp_hour_hand)
        elif hour <= 12:
            hour_hand = basic_hour_hand + ((3 - (hour - 9)) * amp_hour_hand)
        cal_hour = (hour * 30 + 270)
        if cal_hour > 360:
            cal_hour = cal_hour - 360
        rad_min = 3.14159 / 180 * cal_hour
        x = hour_hand * math.cos(rad_min) + timer_x
        y = hour_hand * math.sin(rad_min) + timer_y
        draw.line((timer_x, timer_y, x, y), fill=255)
        font = ImageFont.truetype(self.TEXT_FILE_PATH, font_size)
        x_pos = 67
        y_pos = 18
        if ampm_hour >= 10:
            if minute >= 10:
                draw.text((x_pos, y_pos), str(ampm_hour) + ' : ' + str(minute), font=font, fill=255)
            else:
                draw.text((x_pos, y_pos), str(ampm_hour) + ' : 0' + str(minute), font=font, fill=255)
        else:
            if minute >= 10:
                draw.text((x_pos, y_pos), '  ' + str(ampm_hour) + ' : ' + str(minute), font=font, fill=255)
            else:
                draw.text((x_pos, y_pos), '  ' + str(ampm_hour) + ' : 0' + str(minute), font=font, fill=255)
        length = len(string)
        if length > 8:
            print('Please enter 8 characters or fewer than 8 characters.')
        else:
            font = ImageFont.truetype(self.TEXT_FILE_PATH, 14)
            draw.text((69, 18 + 25), string, font=font, fill=255)
        self.disp.display(image)

    # -------------------------------------------------------------------------
    # Commandes bas-niveau — routées via smbus2 directement
    # luma.oled ne fournit pas d'accès public aux commandes de scroll SSD1306
    # -------------------------------------------------------------------------

    def off(self):
        self.command(self.SSD1306_DISPLAYOFF)

    def on(self):
        self.command(self.SSD1306_DISPLAYON)

    def invert(self):
        self.command(self.SSD1306_INVERTDISPLAY)

    def normal(self):
        self.command(self.SSD1306_NORMALDISPLAY)

    def stop_scroll(self):
        self.command(self.SSD1306_DEACTIVATE_SCROLL)

    def start_scroll(self):
        self.command(self.SSD1306_ACTIVATE_SCROLL)

    def right_scroll(self, start_row=0, end_row=7, time_interval=7):
        self.stop_scroll()
        self.command(self.SSD1306_RIGHT_HORIZONTAL_SCROLL)
        self.command(0x00)
        self.command(start_row)
        self.command(time_interval)
        self.command(end_row)
        self.command(0x00)
        self.command(0xFF)
        self.start_scroll()

    def left_scroll(self, start_row=0, end_row=7, time_interval=7):
        self.stop_scroll()
        self.command(self.SSD1306_LEFT_HORIZONTAL_SCROLL)
        self.command(0x00)
        self.command(start_row)
        self.command(time_interval)
        self.command(end_row)
        self.command(0x00)
        self.command(0xFF)
        self.start_scroll()

    def up_and_left_scroll(self, start_row=0, end_row=7, vert_offset=1, time_interval=7):
        self.stop_scroll()
        self.command(self.SSD1306_VERTICAL_AND_LEFT_HORIZONTAL_SCROLL)
        self.command(0x00)
        self.command(start_row)
        self.command(time_interval)
        self.command(end_row)
        self.command(vert_offset)
        self.start_scroll()

    def up_and_right_scroll(self, start_row=0, end_row=7, vert_offset=1, time_interval=7):
        self.stop_scroll()
        self.command(self.SSD1306_VERTICAL_AND_RIGHT_HORIZONTAL_SCROLL)
        self.command(0x00)
        self.command(start_row)
        self.command(time_interval)
        self.command(end_row)
        self.command(vert_offset)
        self.start_scroll()

    def set_contrast(self, value):
        # PATCH : self.disp.set_contrast() non disponible dans luma.oled
        # Routé directement via smbus2
        self.command(self.SSD1306_SETCONTRAST)
        self.command(value & 0xFF)

    # -------------------------------------------------------------------------
    # Méthodes utilitaires et animations — PATCH : même remplacement d'API
    # -------------------------------------------------------------------------

    def flicker_text(self, string, count=10, delay=0.5):
        if len(string) > 8:
            print('Please enter 8 characters or fewer than 8 characters.')
        else:
            self.clear_display()
            self.draw_text_center(string)
            for i in range(0, count):
                self.on()
                time.sleep(delay + 0.01)
                self.off()
                time.sleep(delay + 0.01)
            self.on()

    def size_text(self, count, size, string):
        if len(string) > 8:
            print('Please enter 8 characters or fewer than 8 characters.')
        else:
            self.draw_text_center(string, font_size=16)
            for i in range(0, count):
                for j in range(16, size, 2):
                    self.draw_text_center(string, font_size=j)
                for j in range(size, 16, -2):
                    self.draw_text_center(string, font_size=j)

    def moving_text(self, direction, string, line=25, speed=5, font_size=16):
        image = Image.new('1', (self.width, self.height))
        font = ImageFont.truetype(self.TEXT_FILE_PATH, font_size)
        draw = ImageDraw.Draw(image)
        size = draw.textsize(string, font=font)
        pos = 128 - size[0]
        length = len(string)
        if 0 <= line <= 45:
            if length > 8:
                print('Please enter 8 characters or fewer than 8 characters.')
            else:
                if direction == 'R':
                    for i in range(0, pos, speed):
                        image = Image.new('1', (self.width, self.height))
                        draw = ImageDraw.Draw(image)
                        draw.text((0 + i, line), string, font=font, fill=255)
                        self.disp.display(image)
                if direction == 'L':
                    for i in range(pos, 0, -speed):
                        image = Image.new('1', (self.width, self.height))
                        draw = ImageDraw.Draw(image)
                        draw.text((0 + i, line), string, font=font, fill=255)
                        self.disp.display(image)
        else:
            print('Lines can be entered from 0 to 45.')

    def clear_display(self):
        # PATCH : self.disp.clear() + self.disp.display() → self.disp.display(image noire)
        blank = Image.new('1', (self.width, self.height))
        self.disp.display(blank)

    def clear_drawing(self):
        # PATCH : self.disp.clear() supprimé — reset du buffer PIL uniquement
        self.screen_image = Image.new('1', (self.width, self.height))
        self.draw = ImageDraw.Draw(self.screen_image)

    def draw_text(self, string, x=1, y=1, display=0, image=0, font_size=16, clear=True):
        if display == 0:
            display = self.disp
        if image == 0:
            image = Image.new('1', (self.width, self.height))
        font = ImageFont.truetype(self.TEXT_FILE_PATH, font_size)
        draw = ImageDraw.Draw(image)
        if clear:
            draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)
        current_x = x
        current_y = y
        max_x = 0
        max_y = 0
        for char in string:
            char_width, char_height = draw.textsize(char, font=font)
            max_x = char_width if max_x < char_width else max_x
            max_y = char_height if max_y < char_height else max_y
            draw.text((current_x, current_y), char, font=font, fill=255)
            current_x += char_width
            if current_x > self.width - max_x:
                current_x = x
                current_y += max_y + 1
        display.display(image)
        self.screen_image = image

    def draw_text_center(self, string, display=0, image=0, font_size=16, clear=True):
        words = string.split(' ')
        split_lines = []
        text = ""
        current_h = font_size
        font = ImageFont.truetype(self.TEXT_FILE_PATH, font_size)
        if display == 0:
            display = self.disp
        if image == 0:
            image = Image.new('1', (self.width, self.height))
        draw = ImageDraw.Draw(image)
        if clear:
            draw.rectangle((0, 0, self.width, self.height), outline=0, fill=0)
        for word in words:
            new_line = False
            new_line_next_word = ""
            if "\n" in word:
                try:
                    word, new_line_next_word = word.split("\n")
                    new_line = True
                except Exception:
                    print("You should use '\\n' only once in one word")
                    return
            text += word + " "
            text_width, text_height = draw.textsize(text, font=font)
            if word == words[0]:
                current_h = text_height
            if text_width >= 124:
                text = text[:-len(word) - 2]
                split_lines.append(text)
                text = word + " "
                current_h += text_height
            if new_line:
                split_lines.append(text[:-1])
                current_h += text_height
                text = new_line_next_word + " "
            if current_h >= 60:
                print("Sentence is too long")
                return
        split_lines.append(text[:-1])
        current_y = (self.height - 4 - current_h) / 2
        for text in split_lines:
            text_width, text_height = draw.textsize(text, font=font)
            current_x = (self.width - text_width) / 2
            draw.text((current_x, current_y), text, font=font, fill=255)
            current_y += text_height
        display.display(image)
        self.screen_image = image

    def path_to_image(self, path):
        return Image.open(path).convert('1')

    def show_image(self, image):
        import cv2
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        small = cv2.resize(gray, (128, 64))
        self.draw_image(Image.fromarray(small).convert('1'))

    def draw_image(self, img, display=0):
        if display == 0:
            display = self.disp
        # PATCH : display.image(img) + display.display() → display.display(img)
        display.display(img)

    def draw_image_by_path(self, path):
        try:
            img = self.path_to_image(path)
            self.draw_image(img)
        except ValueError:
            img = self.path_to_image(path)
            im = img.resize((128, 64))
            self.draw_image(im)

    def draw_image_by_name(self, name):
        self.draw_image(self.path_to_image(self.EYE_IMAGE_FOLDER_PATH + name + ".ppm"))

    def animate(self, preset=None, custom=False):
        preset = self.EXCITED if preset is None else preset
        if not custom:
            for item in preset:
                self.draw_image(self.path_to_image(self.EYE_IMAGE_FOLDER_PATH + item + ".ppm"))
        else:
            for item in preset:
                self.draw_image(item)

    def calibrating(self):
        self.draw_image(self.path_to_image(self.EYE_IMAGE_FOLDER_PATH + "calibrating.ppm"))

    def calibrated(self):
        self.draw_image(self.path_to_image(self.EYE_IMAGE_FOLDER_PATH + "calibrated.ppm"))

    def close_eyes(self):
        self.draw_image(self.path_to_image(self.EYE_IMAGE_FOLDER_PATH + "close.ppm"))

    def sleepy_eyes(self):
        self.draw_image(self.path_to_image(self.EYE_IMAGE_FOLDER_PATH + "sleep.ppm"))

    def sleepy_left(self):
        self.draw_image(self.path_to_image(self.EYE_IMAGE_FOLDER_PATH + "sleepyleft1.ppm"))

    def sleepy_right(self):
        self.draw_image(self.path_to_image(self.EYE_IMAGE_FOLDER_PATH + "sleepyright1.ppm"))

    def blink(self):
        self.draw_image(self.path_to_image(self.EYE_IMAGE_FOLDER_PATH + "neutral2.ppm"))
        time.sleep(.25)
        self.draw_image(self.path_to_image(self.EYE_IMAGE_FOLDER_PATH + "close.ppm"))
        time.sleep(.25)
        self.draw_image(self.path_to_image(self.EYE_IMAGE_FOLDER_PATH + "neutral1.ppm"))

    def look_around_open(self):
        self.draw_image_by_name("lookright1")
        time.sleep(2)
        self.close_eyes()
        self.draw_image_by_name("lookleft1")
        time.sleep(1)
        self.close_eyes()
        self.draw_image_by_name("lookright1")
        time.sleep(1)
        self.close_eyes()
        self.hello()
        time.sleep(1)

    def sleeping(self):
        self.draw_image_by_name("close")
        time.sleep(.6)
        self.draw_image_by_name("sleep_z1")
        time.sleep(.6)
        self.draw_image_by_name("sleep_z2")
        time.sleep(.6)
        self.draw_image_by_name("sleep_z3")
        time.sleep(.6)
        self.draw_image_by_name("close")
        time.sleep(.6)

    def look_around(self):
        self.sleepy_eyes()
        time.sleep(2)
        self.close_eyes()
        self.sleepy_left()
        time.sleep(1)
        self.close_eyes()
        self.sleepy_right()
        time.sleep(1)
        self.close_eyes()
        self.sleepy_eyes()
        time.sleep(1)

    def glimmer(self):
        self.animate(["neutral1", "neutral2", "neutral3"])

    def sad(self):
        self.animate(["sad1"])

    def happy(self):
        self.animate(["neutral1", "neutral2"])
        wink = ["happy_left2", "happy_right1"]
        for i in range(3):
            self.animate(wink)
        self.hello()

    def hello(self):
        self.draw_image(self.path_to_image(self.EYE_IMAGE_FOLDER_PATH + "neutral1.ppm"))

    def angry(self):
        self.draw_image(self.path_to_image(self.EYE_IMAGE_FOLDER_PATH + "focus.ppm"))

    def connection_success(self):
        self.draw_image_by_name("connected")

    def connection_fail(self):
        self.draw_image_by_name("onlinefail")


def run():
    print("test screen.py script")
    eye = Screen()
    print(eye.TEXT_FILE_PATH)
    eye.draw_text("hello world")
    time.sleep(2)
    eye.close_eyes()
    time.sleep(2)
    eye.blink()
    time.sleep(2)
    eye.glimmer()
    time.sleep(2)
    eye.sad()
    time.sleep(2)
    eye.happy()
    time.sleep(2)
    eye.hello()
    print("end test screen.py")


if __name__ == '__main__':
    run()
