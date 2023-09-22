#!/usr/bin/env python3

import time
from rpi_ws281x import PixelStrip, Color


class LEDStrip:
    def __init__(self, LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL):
        # Create NeoPixel object with appropriate configuration.
        self.strip = PixelStrip(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)
        # Initialize the library (must be called once before other functions).
        self.strip.begin()

    def set_pixel_color(self, pixel, color):
        self.strip.setPixelColor(pixel, color)

    def show(self):
        self.strip.show()

    def set_all(self, r, g, b):
        for i in range(self.strip.numPixels()):
            self.set_pixel_color(i, Color(r, g, b))
            self.show()

    def turn_off(self):
        self.set_all(0, 0, 0)

    def color_wipe(self, color, wait_ms=1):
        # Wipe color across display a pixel at a time
        for i in range(self.strip.numPixels()):
            self.set_pixel_color(i, color)
            self.show()
            time.sleep(wait_ms / 1000.0)

    def lightsEndingSequence(self, wait_ms=50):
        # Set all to green
        for i in range(self.strip.numPixels()):
            self.set_pixel_color(i, Color(0, 255, 0))
            self.show()
            time.sleep(wait_ms / 1000.0)

        # Wait a bit and turn off
        time.sleep(2)
        self.turn_off()

    def theater_chase(self, color, wait_ms=50, iterations=10):
        # Movie theater light style chaser animation
        for j in range(iterations):
            for q in range(3):
                for i in range(0, self.strip.numPixels(), 3):
                    self.set_pixel_color(i + q, color)
                self.show()
                time.sleep(wait_ms / 1000.0)
                for i in range(0, self.strip.numPixels(), 3):
                    self.set_pixel_color(i + q, 0)

    @staticmethod
    def wheel(pos):
        # Generate rainbow colors across 0-255 positions
        if pos < 85:
            return Color(pos * 3, 255 - pos * 3, 0)
        elif pos < 170:
            pos -= 85
            return Color(255 - pos * 3, 0, pos * 3)
        else:
            pos -= 170
            return Color(0, pos * 3, 255 - pos * 3)

    def rainbow(self, wait_ms=20, iterations=1):
        # Draw rainbow that fades across all pixels at once
        for j in range(256 * iterations):
            for i in range(self.strip.numPixels()):
                self.set_pixel_color(i, self.wheel((i + j) & 255))
            self.show()
            time.sleep(wait_ms / 1000.0)

    def rainbow_cycle(self, wait_ms=20, iterations=5):
        # Draw rainbow that uniformly distributes itself across all pixels
        for j in range(256 * iterations):
            for i in range(self.strip.numPixels()):
                self.set_pixel_color(i, self.wheel((int(i * 256 / self.strip.numPixels()) + j) & 255))
            self.show()
            time.sleep(wait_ms / 1000.0)

    def theater_chase_rainbow(self, wait_ms=50):
        # Rainbow movie theater light style chaser animation
        for j in range(256):
            for q in range(3):
                for i in range(0, self.strip.numPixels(), 3):
                    self.set_pixel_color(i + q, self.wheel((i + j) % 255))
                self.show()
                time.sleep(wait_ms / 1000.0)
                for i in range(0, self.strip.numPixels(), 3):
                    self.set_pixel_color(i + q, 0)

    def start_up(self):
        self.set_all(255, 255, 255)
