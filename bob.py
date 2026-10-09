# TRI-32 BOB NODE
# ESP32 DevKit V1 / MicroPython
# OLED: SDA=GPIO21, SCL=GPIO22
# Buttons: BB84=GPIO13, Classical=GPIO14, Grover estimate=GPIO27, Reset=GPIO26
# Potentiometer: GPIO34; status LED: GPIO2
#
# IMPORTANT:
# This is a reconstruction from the code visible in the conversation, not a
# byte-for-byte recovery of the original file. QBER/key/search are demonstrations,
# not physical quantum key distribution or a real Grover quantum circuit.

from machine import Pin, SoftI2C, ADC
import ssd1306
import time
import urandom
import network
import espnow
import math

last_dashboard_state = ""
number_array = [12, 7, 25, 3, 18, 40, 29, 15, 9, 31]
target_number = 29
pending_array = []
pending_target = 0
received_array = []
received_target = 0
user_data_ready = False
shared_key = ""
last_dashboard_send = 0
last_qber_send = 0
attack_sent = False
last_bb84_press = 0

i2c = SoftI2C(sda=Pin(21), scl=Pin(22), freq=100000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c)

btn_start_bb84 = Pin(13, Pin.IN, Pin.PULL_UP)
btn_classic = Pin(14, Pin.IN, Pin.PULL_UP)
btn_grover = Pin(27, Pin.IN, Pin.PULL_UP)
btn_reset = Pin(26, Pin.IN, Pin.PULL_UP)

pot_ai = ADC(Pin(34))
pot_ai.atten(ADC.ATTN_11DB)
led_green = Pin(2, Pin.OUT)

def send_dashboard(event, value=""):
    # Serial protocol consumed by the HTML dashboard
    print(f"{event}|{value}")

def update_oled(l1="", l2="", l3="", l4="", delay=0):
    oled.fill(0)
    oled.text(str(l1)[:16], 0, 0)
    oled.text(str(l2)[:16], 0, 16)
    oled.text(str(l3)[:16], 0, 32)
    oled.text(str(l4)[:16], 0, 48)
    oled.show()
    if delay > 0:
        time.sleep(delay)

patient_dna = (
    "ATGTGTGGCATTTGGGCGCTGTTTGGCAGTGATGATTGCCTTTCTGTTCAGTGTCTGAGTGCTATGAAG"
    "ATTGCACACAGAGGTCCAGATGCATTCCGTTTTGAGAATGTCAATGGATACACCAACTGCTGCTTTGGA"
    "TTTCACCGGTTGGCGGTAGTTGACCCGCTGTTTGGAATGCAGCCAATTCGAGTGAAGAAATATCCGTAT"
    "TTGTGGCTCTGTTACAATGGTGAAATCTACAACCATAAGAAGATGCAACAGCATTTTGAATTTGAATAC"
    "CAGACCAAAGTGGATGGTGAGATAATCCTTCATCTTTATGACAAAGGAGGAATTGAGCAAACAATTTGT"
    "ATGTTGGATGGTGTGTTTGCATTTGTTTTACTGGATACTGCCAATAAGAAAGTGTTCCTGGGTAGAGAT"
    "ACATATGGAGTCAGACCTTTGTTTAAAGCAATGACAGAAGATGGATTTTTGGCTGTATGTTCAGAAGCT"
    "AAAGGTCTTGTTACATTGAAGCACTCCGCGACTCCCTTTTTAAAAGTGGAGCCTTTTCTTCCTGGACAC"
    "TATGAAGTTTTGGATTTAAAGCCAAATGGCAAAGTTGCATCCGTGGAAATGGTTAAATATCATCACTGT"
    "CGGGATGTACCCCTGCACGCCCTCTATGACAATGTGGAGAAACTCTTTCCAGGTTTTGAGATAGAAACT"
    "GTGAAGAACAACCTCAGGATCCTTTTTAATAATGCTGTAAAGAAACGTTTGATGACAGACAGAAGGATT"
    "GGCTGCCTTTTATCAGGGGGCTTGGACTCCAGCTTGGTTGCTGCCACTCTGTTGAAGCAGCTGAAAGAA"
    "GCCCAAGTACAGTATCCTCTCCAGACATTTGCAATTGGCATGGAAGACAGCCCCGATTTACTGGCTGCT"
    "AGAAAGGTGGCAGATCATATTGGAAGTGAACATTATGAAGTCCTTTTTAACTCTGAGGAAGGCATTCAG"
    "GCTCTGGATGAAGTCATATTTTCCTTGGAAACTTATGACATTACAACAGTTCGTGCTTCAGTAGGTATG"
    "TATTTAATTTCCAAGTATATTCGGAAGAACACAGATAGCGTGGTGATCTTCTCTGGAGAAGGATC"
)
target_mutation = "TAGGTATGTATTTAA"
N = len(patient_dna) - len(target_mutation) + 1

system_state = "IDLE"
qber_buffer = []
current_qber = 2.1
alice_bases_stream = "+x++xx"

def flush_espnow():
    while True:
        host, msg = e.recv(0)
        if not msg:
            break

def edge_ai_anomaly_scan(new_qber, ai_sens):
    global qber_buffer
    qber_buffer.append(new_qber)
    if len(qber_buffer) > 20:
        qber_buffer.pop(0)
    if len(qber_buffer) < 5:
        return False
    mean = sum(qber_buffer) / len(qber_buffer)
    variance = sum((x - mean) ** 2 for x in qber_buffer) / len(qber_buffer)
    if variance < 0.1:
        variance = 0.1
    z_score = abs(new_qber - mean) / math.sqrt(variance)
    return z_score > ai_sens

def classical_search(arr, target):
    steps = 0
    for i in range(len(arr)):
        steps += 1
        if arr[i] == target:
            return i, steps
    return -1, steps

def grover_search_estimate(arr, target):
    # Complexity illustration only; this does not execute Grover's algorithm.
    size = len(arr)
    grover_steps = int((math.pi / 4) * math.sqrt(size))
    found_index = -1
    for i in range(len(arr)):
        if arr[i] == target:
            found_index = i
            break
    return found_index, grover_steps

def dna_classical_search():
    found_index = patient_dna.find(target_mutation)
    classical_steps = max(found_index, 0)
    return found_index, classical_steps

def dna_grover_search():
    # Classical string lookup plus a theoretical Grover iteration estimate.
    found_index = patient_dna.find(target_mutation)
    grover_steps = int((math.pi / 4) * math.sqrt(N))
    return found_index, grover_steps

sta = network.WLAN(network.STA_IF)
sta.active(True)
sta.config(channel=1)
sta.disconnect()

e = espnow.ESPNow()
e.active(True)

update_oled("SYSTEM BOOT", "Initializing", "Quantum Node", "BOB READY", delay=2)
last_idle_refresh = time.ticks_ms()

while True:
    if system_state == "LOCKED":
        led_green.value(1)
        update_oled("!!! SYSTEM !!!", "EVE ATTACKING", "CHANNEL DEAD", "PRESS RESET")
        time.sleep(0.1)
        led_green.value(0)
        time.sleep(0.1)
        if btn_reset.value() == 0:
            system_state = "IDLE"
            qber_buffer = []
            current_qber = 2.1
            flush_espnow()
            send_dashboard("RESET", "TRUE")
            update_oled("SYSTEM RESET", "Reinitializing", "Quantum Node", "Please Wait", delay=2)
        continue

    ai_sens = 1.0 + (pot_ai.read() / 4095.0) * 4.0

    if system_state == "IDLE":
        if last_dashboard_state != "IDLE":
            send_dashboard("STATE", "IDLE")
            last_dashboard_state = "IDLE"
        if time.ticks_diff(time.ticks_ms(), last_idle_refresh) > 1000:
            update_oled("SYSTEM IDLE", f"Sens:{ai_sens:.1f}", f"QBER:{current_qber:.1f}", "BTN13 START")
            last_idle_refresh = time.ticks_ms()

    host, msg = e.recv(0)
    if msg:
        try:
            data = msg.decode().split("|")
            msg_type = int(data[0])

            if msg_type == 1:
                current_qber = urandom.uniform(1.0, 3.0)
                edge_ai_anomaly_scan(current_qber, ai_sens)
                alice_bases_stream = data[1] if len(data) > 1 else "+x++xx"
                send_dashboard("QBER", round(current_qber, 2))
                send_dashboard("CHANNEL", "SECURE")

            elif msg_type == 2:
                current_qber = urandom.uniform(40.0, 50.0)
                send_dashboard("QBER", round(current_qber, 2))
                send_dashboard("ATTACK", "EVE_DETECTED")
                send_dashboard("CHANNEL", "COLLAPSED")
                update_oled("!!! ALERT !!!", "EVE ATTACK", f"QBER:{current_qber:.1f}", "CHANNEL HIT", delay=2)
                system_state = "LOCKED"

            elif msg_type == 3:
                pending_array = [int(x) for x in data[1].split(",")]
                pending_target = int(data[2])
                send_dashboard("PENDING_TARGET", pending_target)
                update_oled("USER DATA RX", f"N:{len(pending_array)}", f"T:{pending_target}", "PRESS BTN1", delay=2)

        except Exception as ex:
            print("ERROR:", ex)

    if btn_start_bb84.value() == 0 and system_state == "IDLE":
        now = time.ticks_ms()
        if time.ticks_diff(now, last_bb84_press) > 1500:
            last_bb84_press = now
            system_state = "EXCHANGE"
            send_dashboard("STATE", "EXCHANGE")
            update_oled("BB84 START", "Generating", "Quantum Key", "Please Wait", delay=2)

            if len(pending_array) > 0:
                received_array = pending_array
                received_target = pending_target
                user_data_ready = True

            for _ in range(5):
                led_green.value(1)
                time.sleep(0.1)
                led_green.value(0)
                bob_bases = "".join([urandom.choice(["+", "x"]) for _ in range(8)])
                send_dashboard("BOB_BASES", bob_bases)
                update_oled("BB84 EXCHANGE", f"A:{alice_bases_stream}", f"B:{bob_bases}", "Comparing...", delay=1)

                t_start = time.ticks_ms()
                while time.ticks_diff(time.ticks_ms(), t_start) < 1000:
                    host, msg = e.recv(0)
                    if msg:
                        try:
                            rx = msg.decode().split("|")
                            if int(rx[0]) == 2:
                                current_qber = urandom.uniform(40.0, 50.0)
                                if edge_ai_anomaly_scan(current_qber, ai_sens):
                                    system_state = "LOCKED"
                                    send_dashboard("STATE", "LOCKED")
                                    break
                        except Exception as ex:
                            print("RX ERROR:", ex)

                if system_state == "LOCKED":
                    break

            if system_state == "EXCHANGE":
                system_state = "SECURE"
                attack_sent = False
                send_dashboard("STATE", "SECURE")
                shared_key = "".join([urandom.choice(["1", "0"]) for _ in range(12)])
                send_dashboard("KEY", shared_key)
                update_oled("BB84 SUCCESS", f"KEY:{shared_key}", "CHANNEL SAFE", "READY SEARCH", delay=3)

    if system_state == "SECURE" and btn_classic.value() == 0:
        if user_data_ready:
            found_index, classical_steps = classical_search(received_array, received_target)
            target_label = str(received_target)
        else:
            found_index, classical_steps = dna_classical_search()
            target_label = "BRAF"

        update_oled("CLASSICAL", "O(N)", f"T:{target_label}", "RUNNING", delay=1)
        for i in range(classical_steps):
            send_dashboard("CLASSICAL_PROGRESS", i)
            update_oled("CLASSICALSCAN", f"STEP:{i+1}", "Searching", "Linear Scan")
            time.sleep(0.03)
        update_oled("TARGET FOUND", f"Idx:{found_index}", "CLASSICAL", f"STEP:{classical_steps}", delay=4)

    if system_state == "SECURE" and btn_grover.value() == 0:
        send_dashboard("SEARCH_RESULT", "GROVER_RUNNING")
        update_oled("GROVER SEARCH", "O(ROOT N)", "AMPLIFYING", "PROBABILITY", delay=2)

        if user_data_ready:
            found_index, grover_steps = grover_search_estimate(received_array, received_target)
        else:
            found_index, grover_steps = dna_grover_search()

        for i in range(grover_steps):
            send_dashboard("GROVER_PROGRESS", i + 1)
            update_oled("GROVER SEARCH", f"STEP:{i+1}/{grover_steps}", "Quantum Scan", "Amplifying")
            time.sleep(0.15)

        send_dashboard("GROVER_STEPS", grover_steps)
        update_oled("TARGET FOUND", f"Idx:{found_index}", "GROVER FAST", f"STEP:{grover_steps}", delay=4)

    if btn_reset.value() == 0:
        system_state = "IDLE"
        qber_buffer = []
        attack_sent = False
        user_data_ready = False
        pending_array = []
        pending_target = 0
        received_array = []
        received_target = 0
        flush_espnow()
        send_dashboard("RESET", "TRUE")
        update_oled("SYSTEM RESET", "Flushing AI", "Restarting", "Please Wait", delay=2)

    time.sleep(0.01)
