import time
import board

import digitalio
from adafruit_pn532.spi import PN532_SPI

print("PN532 SPI: SCK=A1 MISO=A2 MOSI=A3 SS=A6")
print("Reader schakelaars: 1=OFF, 2=ON")
class SoftwareSPI:
    def __init__(self, clock, MOSI, MISO):
        self.clock = digitalio.DigitalInOut(clock)
        self.clock.switch_to_output(value=False)
        self.mosi = digitalio.DigitalInOut(MOSI)
        self.mosi.switch_to_output(value=False)
        self.miso = digitalio.DigitalInOut(MISO)
        self.miso.switch_to_input()
        self.locked = False
    def try_lock(self):
        if self.locked:
            return False
        self.locked = True
        return True
    def unlock(self):
        self.locked = False
    def configure(self, baudrate=100000, polarity=0, phase=0, bits=8):
        if polarity or phase or bits != 8:
            raise ValueError("Alleen SPI mode 0, 8 bits ondersteund")
    def transfer(self, value):
        result = 0
        for shift in range(7, -1, -1):
            self.mosi.value = bool(value & (1 << shift))
            time.sleep(0.00001)
            self.clock.value = True
            time.sleep(0.00001)
            result = (result << 1) | int(self.miso.value)
            self.clock.value = False
        return result
    def write(self, buffer, *, start=0, end=None):
        if end is None:
            end = len(buffer)
        for pos in range(start, end):
            self.transfer(buffer[pos])
    def readinto(self, buffer, *, start=0, end=None, write_value=0):
        if end is None:
            end = len(buffer)
        for pos in range(start, end):
            buffer[pos] = self.transfer(write_value)
    def write_readinto(self, outgoing, incoming, *, out_start=0, out_end=None, in_start=0, in_end=None):
        if out_end is None:
            out_end = len(outgoing)
        if in_end is None:
            in_end = len(incoming)
        if out_end-out_start != in_end-in_start:
            raise ValueError("Buffers moeten even lang zijn")
        for offset in range(out_end-out_start):
            incoming[in_start+offset] = self.transfer(outgoing[out_start+offset])
    def deinit(self):
        self.clock.deinit()
        self.mosi.deinit()
        self.miso.deinit()

spi = SoftwareSPI(board.A1, MOSI=board.A3, MISO=board.A2)
cs = digitalio.DigitalInOut(board.A6)
cs.switch_to_output(value=True)
led = digitalio.DigitalInOut(board.D13)
led.switch_to_output(value=False)

while True:
    try:
        reader = PN532_SPI(spi, cs, debug=False)
        chip, major, minor, support = reader.firmware_version
        print("PN532 GEVONDEN, firmware {}.{}".format(major, minor))
        reader.SAM_configuration()
        print("KLAAR: houd een 13,56 MHz kaart bij de reader")
        last_uid = None
        last_seen = 0
        while True:
            uid = reader.read_passive_target(timeout=0.5)
            now = time.monotonic()
            if uid is not None:
                card = "-".join("{:02X}".format(b) for b in uid)
                if card != last_uid or now-last_seen > 2:
                    print("Kaart gelezen:", card)
                    led.value = True
                    time.sleep(0.15)
                    led.value = False
                last_uid = card
                last_seen = now
            time.sleep(0.05)
    except (RuntimeError, ValueError, OSError) as error:
        led.value = False
        cs.value = True
        print("SPI verbinding mislukt:", repr(error))
        print("Nieuwe poging over 5 seconden")
        time.sleep(5)