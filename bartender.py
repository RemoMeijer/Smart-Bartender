import json
import threading
import time
import traceback

import Adafruit_GPIO.SPI as SPI
import Adafruit_SSD1306
import RPi.GPIO as GPIO

from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from gpiozero import DistanceSensor
from LedControl import LEDStrip

from menu import MenuItem, Menu, Back, MenuContext, MenuDelegate

GPIO.setmode(GPIO.BCM)

# OLED init
disp = Adafruit_SSD1306.SSD1306_128_64(rst=24, dc=23, spi=SPI.SpiDev(0, 0, max_speed_hz=8000000))
disp.begin()
disp.clear()
disp.display()

disp2 = Adafruit_SSD1306.SSD1306_128_64(rst=24, dc=23, spi=SPI.SpiDev(0, 0, max_speed_hz=8000000))
disp2.begin()
disp2.clear()
disp2.display()

# Button pins
LEFT_BTN_PIN = 4
RIGHT_BTN_PIN = 25

# LED strip init
LED_COUNT = 30
LED_PIN = 18
LED_FREQ_HZ = 800000
LED_DMA = 10
LED_INVERT = False
LED_BRIGHTNESS = 255
LED_CHANNEL = 0
strip = LEDStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)

# Ultrasonic init
TRIGGER_PIN = 22
ECHO_PIN = 27
GLASS_DETECTION_RANGE = 10

FLOW_RATE = 5


def calculateGlassDistance():
    ultrasonic = DistanceSensor(echo=ECHO_PIN, trigger=TRIGGER_PIN)
    # Need to convert to cm
    return ultrasonic.distance * 100


def displayOLEDText(display, text):
    display.clear()

    image = Image.new('1', (display.width, display.height))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('LDFComicSans.ttf', 40)
    draw.text((10, 10), text, font=font, fill=255)

    display.image(image)
    display.display()


class Bartender(MenuDelegate):
    def __init__(self):
        self.running = False

        self.btn1Pin = LEFT_BTN_PIN
        self.btn2Pin = RIGHT_BTN_PIN

        # configure interrupts for buttons
        GPIO.setup(self.btn1Pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(self.btn2Pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

        GPIO.setup(TRIGGER_PIN, GPIO.OUT)
        GPIO.setup(ECHO_PIN, GPIO.IN)

        # load the pump configuration from file
        self.pump_configuration = Bartender.readPumpConfiguration()
        for pump in self.pump_configuration.keys():
            GPIO.setup(self.pump_configuration[pump]["pin"], GPIO.OUT, initial=GPIO.HIGH)

        # turn everything off
        strip.start_up()
        strip.turn_off()

        print("Done initializing")

    @staticmethod
    def readPumpConfiguration():
        return json.load(open('pump_config.json'))

    @staticmethod
    def writePumpConfiguration(configuration):
        with open("pump_config.json", "w") as jsonFile:
            json.dump(configuration, jsonFile)

    def startInterrupts(self):
        GPIO.add_event_detect(self.btn1Pin, GPIO.RISING, callback=self.left_btn)
        GPIO.add_event_detect(self.btn2Pin, GPIO.RISING, callback=self.right_btn)

    def stopInterrupts(self):
        GPIO.remove_event_detect(self.btn1Pin)
        GPIO.remove_event_detect(self.btn2Pin)

    def buildMenu(self, drink_list, drink_options):
        # create a new main menu
        m = Menu("Main Menu")

        # add drink options
        drink_opts = []
        for d in drink_list:
            drink_opts.append(MenuItem('drink', d["name"], {"ingredients": d["ingredients"]}))

        configuration_menu = Menu("Configure")

        # add pump configuration options
        pump_opts = []
        for p in sorted(self.pump_configuration.keys()):
            config = Menu(self.pump_configuration[p]["name"])
            # add fluid options for each pump
            for opt in drink_options:
                # star the selected option
                selected = "*" if opt["value"] == self.pump_configuration[p]["value"] else ""
                config.addOption(
                    MenuItem('pump_selection', opt["name"], {"key": p, "value": opt["value"], "name": opt["name"]}))
            # add a back button so the user can return without modifying
            config.addOption(Back("Back"))
            config.setParent(configuration_menu)
            pump_opts.append(config)

        # add pump menus to the configuration menu
        configuration_menu.addOptions(pump_opts)
        # add a back button to the configuration menu
        configuration_menu.addOption(Back("Back"))
        # adds an option that cleans all pumps to the configuration menu
        configuration_menu.addOption(MenuItem('clean', 'Clean'))
        configuration_menu.setParent(m)

        m.addOptions(drink_opts)
        m.addOption(configuration_menu)
        # create a menu context
        self.menuContext = MenuContext(m, self)

    def filterDrinks(self, menu):
        # Removes any drinks that can't be handled by the pump configuration
        for i in menu.options:
            if i.type == "drink":
                i.visible = False
                ingredients = i.attributes["ingredients"]
                presentIng = 0
                for ing in ingredients.keys():
                    for p in self.pump_configuration.keys():
                        if ing == self.pump_configuration[p]["value"]:
                            presentIng += 1
                if presentIng == len(ingredients.keys()):
                    i.visible = True
            elif i.type == "menu":
                self.filterDrinks(i)

    def selectConfigurations(self, menu):
        # Adds a selection star to the pump configuration option
        for i in menu.options:
            if i.type == "pump_selection":
                key = i.attributes["key"]
                if self.pump_configuration[key]["value"] == i.attributes["value"]:
                    i.name = "%s %s" % (i.attributes["name"], "*")
                else:
                    i.name = i.attributes["name"]
            elif i.type == "menu":
                self.selectConfigurations(i)

    def prepareForRender(self, menu):
        self.filterDrinks(menu)
        self.selectConfigurations(menu)
        return True

    def menuItemClicked(self, menuItem):
        if menuItem.type == "drink":
            self.makeDrink(menuItem.name, menuItem.attributes["ingredients"])
            return True
        elif menuItem.type == "pump_selection":
            self.pump_configuration[menuItem.attributes["key"]]["value"] = menuItem.attributes["value"]
            Bartender.writePumpConfiguration(self.pump_configuration)
            return True
        elif menuItem.type == "clean":
            self.clean()
            return True
        return False

    def clean(self):
        waitTime = 20
        pumpThreads = []

        # cancel any button presses while the drink is being made
        self.stopInterrupts()
        self.running = True

        # Set LED to red when cleaning
        light_thread = threading.Thread(target=strip.set_all(255, 0, 0))
        light_thread.start()

        for pump in self.pump_configuration.keys():
            pump_t = threading.Thread(target=self.pour, args=(self.pump_configuration[pump]["pin"], waitTime))
            pumpThreads.append(pump_t)

        # start the pump threads
        for thread in pumpThreads:
            thread.start()

        # start the progress bar
        self.progressBar(waitTime)

        # wait for threads to finish
        for thread in pumpThreads:
            thread.join()

        # show the main menu
        self.menuContext.showMenu()

        # sleep for a couple seconds to make sure the interrupts don't get triggered
        time.sleep(2)

        # re-enable interrupts
        self.startInterrupts()
        self.running = False

    def displayMenuItem(self, menuItem):
        print(menuItem.name)
        first_part = menuItem.name
        second_part = ""

        # Split string if too large
        if len(menuItem.name) > 6:
            first_part = menuItem.name[:6]
            second_part = menuItem.name[6:]

        displayOLEDText(disp, first_part)
        displayOLEDText(disp2, second_part)

    def pour(self, pin, waitTime):
        # Set pump active for wait time
        GPIO.output(pin, GPIO.LOW)
        time.sleep(waitTime)
        GPIO.output(pin, GPIO.HIGH)

    def progressBar(self, waitTime):
        interval = waitTime / 100.0
        for x in range(1, 101):
            self.updateProgressBar(str(x))
            time.sleep(interval)

    def makeDrink(self, drink, ingredients):
        # Cancel any button presses while the drink is being made
        self.stopInterrupts()
        self.running = True

        # launch a thread to control lighting
        lightsThread = threading.Thread(target=strip.rainbow())
        lightsThread.start()

        # Set distance over the range, so we won't skip the loop
        distance = GLASS_DETECTION_RANGE

        # Wait until glass is placed
        while distance > GLASS_DETECTION_RANGE:
            displayOLEDText(disp, "No glass")
            distance = calculateGlassDistance()
            time.sleep(0.2)

        displayOLEDText(disp, "Glass")
        displayOLEDText(disp2, "Detected")
        time.sleep(0.5)

        # Parse the drink ingredients and spawn threads for pumps
        maxTime = 0
        pumpThreads = []
        for ing in ingredients.keys():
            for pump in self.pump_configuration.keys():
                if ing == self.pump_configuration[pump]["value"]:
                    waitTime = ingredients[ing] * FLOW_RATE
                    if waitTime > maxTime:
                        maxTime = waitTime
                    pump_t = threading.Thread(target=self.pour, args=(self.pump_configuration[pump]["pin"], waitTime))
                    pumpThreads.append(pump_t)

        # Start the pump threads
        for thread in pumpThreads:
            thread.start()

        displayOLEDText(disp, "Pouring")

        # Start the progress bar
        self.progressBar(maxTime)

        # Wait for threads to finish
        for thread in pumpThreads:
            thread.join()

        # Show the main menu
        self.menuContext.showMenu()

        # Stop the light thread
        lightsThread.do_run = False
        lightsThread.join()

        # Show the ending sequence lights
        strip.lightsEndingSequence()

        # sleep for a couple seconds to make sure the interrupts don't get triggered
        time.sleep(2)

        # re-enable interrupts
        self.startInterrupts()
        self.running = False

    def left_btn(self):
        if not self.running:
            self.menuContext.advance()

    def right_btn(self):
        if not self.running:
            self.menuContext.select()

    def updateProgressBar(self, percent):
        displayOLEDText(disp2, f"{percent}%")

    def run(self):
        self.startInterrupts()

        # main loop
        try:
            while True:
                time.sleep(1)

        except KeyboardInterrupt:
            GPIO.cleanup()  # clean up GPIO on CTRL+C exit
        GPIO.cleanup()  # clean up GPIO on normal exit

        traceback.print_exc()
