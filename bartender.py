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
from LedControl import LEDStrip
from drinks import drink_list, drink_options

import faulthandler

from menu import MenuItem, Menu, Back, MenuContext, MenuDelegate

# OLED init lock Frequency set to 10MHz from 8 MHz
disp = Adafruit_SSD1306.SSD1306_128_64(rst=24, dc=23, spi=SPI.SpiDev(0, 0, max_speed_hz=8000000))
disp_cs_pin = 7

disp2 = Adafruit_SSD1306.SSD1306_128_64(rst=24, dc=23, spi=SPI.SpiDev(0, 0, max_speed_hz=8000000))
disp2_cs_pin = 8

# Button pins
LEFT_BTN_PIN = 25
RIGHT_BTN_PIN = 4

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
TRIGGER_PIN = 27
ECHO_PIN = 22
GLASS_DETECTION_RANGE_MAX = 20
GLASS_DETECTION_RANGE_MIN = 10

# Flow rate of the pumps
FLOW_RATE = 0.033


def calculateGlassDistance():
    # set Trigger to HIGH
    GPIO.output(TRIGGER_PIN, True)

    # set Trigger after 0.01ms to LOW
    time.sleep(0.00001)
    GPIO.output(TRIGGER_PIN, False)

    StartTime = time.time()
    StopTime = time.time()

    # save StartTime
    while GPIO.input(ECHO_PIN) == 0:
        StartTime = time.time()

    # save time of arrival
    while GPIO.input(ECHO_PIN) == 1:
        StopTime = time.time()

    # time difference between start and arrival
    TimeElapsed = StopTime - StartTime
    # multiply with the sonic speed (34300 cm/s)
    # and divide by 2, because there and back
    distance = (TimeElapsed * 34300) / 2

    return distance


def displayOLEDText(display, cs_pin, text):
    GPIO.output(cs_pin, GPIO.LOW)  # Turn on the display
    display.clear()

    image = Image.new('1', (display.width, display.height))
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype('LDFComicSans.ttf', 40)
    draw.text((10, 10), text, font=font, fill=255)

    display.image(image)
    display.display()
    GPIO.output(cs_pin, GPIO.HIGH)  # Turn off the display


class Bartender(MenuDelegate):
    def __init__(self):
        GPIO.setmode(GPIO.BCM)
        self.running = False
        self.makingDrink = False
        self.enableInterrupts = False

        faulthandler.enable()

        self.btn1Pin = LEFT_BTN_PIN
        self.btn2Pin = RIGHT_BTN_PIN

        # Configure interrupts for buttons
        GPIO.setup(self.btn1Pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
        GPIO.setup(self.btn2Pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)

        # Configure Ultrasonic device
        GPIO.setup(TRIGGER_PIN, GPIO.OUT)
        GPIO.setup(ECHO_PIN, GPIO.IN)

        GPIO.setup(disp_cs_pin, GPIO.OUT)
        GPIO.setup(disp2_cs_pin, GPIO.OUT)

        # Set display off
        GPIO.output(disp_cs_pin, GPIO.LOW)
        GPIO.output(disp2_cs_pin, GPIO.LOW)

        disp.begin()
        disp.clear()
        disp.display()

        disp2.begin()
        disp2.clear()
        disp2.display()

        # Load the pump configuration from file
        self.pump_configuration = Bartender.readPumpConfiguration()
        for pump in self.pump_configuration.keys():
            GPIO.setup(self.pump_configuration[pump]["pin"], GPIO.OUT, initial=GPIO.HIGH)

        print("Done initializing")

    @staticmethod
    def readPumpConfiguration():
        return json.load(open('pump_config.json'))

    @staticmethod
    def writePumpConfiguration(configuration):
        with open("pump_config.json", "w") as jsonFile:
            json.dump(configuration, jsonFile)

    def startInterrupts(self):
        GPIO.add_event_detect(self.btn1Pin, GPIO.RISING, callback=self.left_btn, bouncetime=400)
        GPIO.add_event_detect(self.btn2Pin, GPIO.RISING, callback=self.right_btn, bouncetime=800)

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
            self.makeDrink(menuItem.attributes["ingredients"])
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
        # Cancel any button presses while the drink is being made
        self.stopInterrupts()
        self.running = True
        self.makingDrink = True

        strip.setAll(0, 0, 255)

        displayOLEDText(disp, disp_cs_pin, "Clean")
        displayOLEDText(disp2, disp2_cs_pin, "ing")

        waitTime = 5
        pumpThreads = []

        for pump in self.pump_configuration.keys():
            pump_t = threading.Thread(target=self.pour, args=(self.pump_configuration[pump]["pin"], waitTime))
            pumpThreads.append(pump_t)

        # Start the pump threads
        for thread in pumpThreads:
            thread.start()

        # Start the progress bar
        self.progressBar(waitTime)

        # Wait for threads to finish
        for thread in pumpThreads:
            thread.join()

        displayOLEDText(disp, disp_cs_pin, "Done c")
        displayOLEDText(disp2, disp2_cs_pin, "leaning")

        self.makingDrink = False
        self.enableInterrupts = True

        return

    def displayMenuItem(self, menuItem):
        print(menuItem.name)
        first_part = menuItem.name
        second_part = ""

        # Split string if too large
        if len(menuItem.name) > 6:
            first_part = menuItem.name[:6]
            second_part = menuItem.name[6:]

        displayOLEDText(disp, disp_cs_pin, first_part)
        displayOLEDText(disp2, disp2_cs_pin, second_part)

    @staticmethod
    def pour(pin, waitTime):
        # Set pump active for wait time
        print(f"Pouring pin {pin}")
        GPIO.output(pin, GPIO.LOW)
        time.sleep(waitTime)
        GPIO.output(pin, GPIO.HIGH)

    def progressBar(self, waitTime):
        interval = (waitTime / 100.0) * 5
        for x in range(1, 21):
            self.updateProgressBar(str(x * 5))
            time.sleep(interval)

    def returnMakingDrink(self):
        return self.makingDrink

    def makeDrink(self, ingredients):
        # Cancel any button presses while the drink is being made
        self.stopInterrupts()
        self.running = True
        self.makingDrink = True

        strip.setAll(255, 0, 0)

        # Set distance over the range, so we won't skip the loop
        distance = 0
        # Display No Glass msg before loop to keep second oled from stuttering
        displayOLEDText(disp, disp_cs_pin, "No")
        displayOLEDText(disp2, disp2_cs_pin, "Glass")
        # Wait until glass is placed
        while distance > GLASS_DETECTION_RANGE_MAX or distance < GLASS_DETECTION_RANGE_MIN:
            distance = calculateGlassDistance()
            time.sleep(0.1)

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
        # Display pouring
        displayOLEDText(disp, disp_cs_pin, "Pour")
        # start progress bar
        self.progressBar(maxTime)

        # Wait for threads to finish
        for thread in pumpThreads:
            thread.join()
        # Move Glass instead of Remove Glass to fit in screen
        displayOLEDText(disp, disp_cs_pin, "Move")
        displayOLEDText(disp2, disp2_cs_pin, "Glass")

        distance = 15
        while GLASS_DETECTION_RANGE_MAX > distance > GLASS_DETECTION_RANGE_MIN:
            strip.setAll(0, 255, 0)
            time.sleep(0.1)
            distance = calculateGlassDistance()
            print(f"distance: {distance}cm")

        print("Glass removed")
        self.makingDrink = False
        self.enableInterrupts = True

        return

    def left_btn(self, button=None):
        if not self.running:
            self.menuContext.advance()

    def right_btn(self, button=None):
        if not self.running:
            self.menuContext.select()

    @staticmethod
    def updateProgressBar(percent):
        # On disp2, because disp1 already states: "Pouring"
        displayOLEDText(disp2, disp2_cs_pin, f"{percent}%")

    def enableInterruptsAgain(self):
        time.sleep(1)
        self.startInterrupts()
        self.running = False

    def run(self):
        self.startInterrupts()

        # main loop
        try:
            while True:
                if self.enableInterrupts:
                    setToFalseThread = threading.Thread(target=self.enableInterruptsAgain())
                    setToFalseThread.start()
                    setToFalseThread.join()
                    self.enableInterrupts = False

                if not self.makingDrink:
                    strip.idle()

                time.sleep(0.1)

        except KeyboardInterrupt:
            GPIO.cleanup()  # clean up GPIO on CTRL+C exit
        GPIO.cleanup()  # clean up GPIO on normal exit

        traceback.print_exc()
