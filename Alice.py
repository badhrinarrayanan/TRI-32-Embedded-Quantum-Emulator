
import network, espnow, urandom, time
from machine import Pin

led = Pin(2, Pin.OUT)

sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.config(channel=1)
sta.disconnect()

e = espnow.ESPNow()
e.active(True)

broadcast_mac = b'\xff\xff\xff\xff\xff\xff'

try:
    e.add_peer(broadcast_mac)
except:
    pass

print("ALICE: Broadcasting background traffic...")

counter = 0

while True:
    bases = "".join([
        urandom.choice(['+', 'x'])
        for _ in range(8)
    ])

    try:
        e.send(broadcast_mac, f"1|{bases}")

        # Toggle LED every 10 iterations
        if counter % 10 == 0:
            led.value(not led.value())

    except:
        pass

    counter += 1
    time.sleep(0.1)
