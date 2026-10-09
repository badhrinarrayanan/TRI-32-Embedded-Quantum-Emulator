# TRI-32 EVE NODE (RECONSTRUCTED)
# ESP32 DevKit V1 / MicroPython
#
# This is a reconstructed companion script, not the exact original Eve file:
# the original complete Eve source was not present in the available conversation.
# It sends protocol message "2|EVE_ATTACK", which Bob's code interprets as an attack.
#
# Wiring:
#   GPIO13 -> push button -> GND (internal pull-up enabled)
#   GPIO2  -> status LED (optional)
# All ESP-NOW nodes must use the same Wi-Fi channel (channel 1).

from machine import Pin
import time
import network
import espnow

attack_button = Pin(13, Pin.IN, Pin.PULL_UP)
status_led = Pin(2, Pin.OUT)

sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.config(channel=1)
sta.disconnect()

e = espnow.ESPNow()
e.active(True)

broadcast_mac = b"\\xff\\xff\\xff\\xff\\xff\\xff"
try:
    e.add_peer(broadcast_mac)
except Exception:
    pass

print("EVE: Ready. Press GPIO13 button to inject attack messages.")
print("EVE protocol: 2|EVE_ATTACK")

last_press = 0
button_was_pressed = False

while True:
    pressed = attack_button.value() == 0
    now = time.ticks_ms()

    # Send once on each new button press, then repeat while held every 300 ms.
    if pressed and (not button_was_pressed or time.ticks_diff(now, last_press) >= 300):
        try:
            e.send(broadcast_mac, "2|EVE_ATTACK")
            status_led.value(1)
            print("EVE: ATTACK MESSAGE SENT")
            time.sleep(0.05)
            status_led.value(0)
        except Exception as ex:
            print("EVE SEND ERROR:", ex)
        last_press = time.ticks_ms()

    button_was_pressed = pressed
    time.sleep(0.02)
