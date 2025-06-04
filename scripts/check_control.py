#!/usr/bin/env python3
import serial
import time
import sys
import threading

# ================= CONFIG =================
SERIAL_PORT = '/dev/ttyUSB0'
BAUDRATE    = 115200

def send_twist(ser, lin, ang):
    frame = f'<V,{lin:.2f},{ang:.2f}>\n'
    ser.write(frame.encode())
    print(f"  → SENT: {frame.strip()}")

def wait_secs(seconds):
    for i in range(int(seconds), 0, -1):
        sys.stdout.write(f"\r    …waiting {i:2d}s ")
        sys.stdout.flush()
        time.sleep(1)
    sys.stdout.write("\r    …continuing now   \n")
    sys.stdout.flush()

import re
import os
import sys
import time

# Terminal colors
RESET = "\033[0m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BOLD = "\033[1m"

ODO = None
STATE = None
LAST_CMD = None
LAST_MSG = None

def clear_screen():
    # Only on real terminals
    if sys.stdout.isatty():
        print("\033c", end='')

def print_table():
    clear_screen()
    print(f"{BOLD}==== ROBOT TELEMETRY ===={RESET}")
    if ODO:
        print(f"{CYAN}Odometry:{RESET}")
        print(f"  ẋ:   {ODO['lin']:.3f} m/s")
        print(f"  θ̇:   {ODO['ang']:.3f} rad/s")
        print(f"  θ:    {ODO['theta']:.3f}°")
        print(f"  Δx:   {ODO['dlin']:.3f}")
        print(f"  Δθ:   {ODO['dang']:.3f}")
    else:
        print(f"{CYAN}Odometry: ...{RESET}")

    if STATE:
        print(f"\n{MAGENTA}State:{RESET}")
        print(f"  t:    {STATE['ts']}")
        print(f"  FL:   {STATE['fl']}    FR: {STATE['fr']}")
        print(f"  RL:   {STATE['rl']}    RR: {STATE['rr']}")
        print(f"  lin:  {STATE['lin']:.3f}   ang: {STATE['ang']:.3f}")
        print(f"  θ:    {STATE['theta']:.3f}  Δx: {STATE['dlin']:.3f}  Δθ: {STATE['dang']:.3f}")
    else:
        print(f"{MAGENTA}State: ...{RESET}")

    if LAST_CMD:
        print(f"\n{GREEN}Last Command:{RESET} {LAST_CMD}")
    if LAST_MSG:
        print(f"\n{YELLOW}Other:{RESET} {LAST_MSG}")

def print_pretty(line):
    global ODO, STATE, LAST_CMD, LAST_MSG

    # ODO
    m = re.match(r"<O,([-\d\.]+),([-\d\.]+),([-\d\.]+),([-\d\.]+),([-\d\.]+)>", line)
    if m:
        ODO = {
            "lin": float(m.group(1)),
            "ang": float(m.group(2)),
            "theta": float(m.group(3)),
            "dlin": float(m.group(4)),
            "dang": float(m.group(5)),
        }
        print_table()
        return

    # STATE
    m = re.match(r"<S,([\d\.]+),([-\d]+),([-\d]+),([-\d]+),([-\d]+),([-\d\.]+),([-\d\.]+),([-\d\.]+),([-\d\.]+),([-\d\.]+),([-\d\.]+),([-\d\.]+),([-\d\.]+),([-\d\.]+)>", line)
    if m:
        STATE = {
            "ts": int(float(m.group(1))),
            "fl": int(float(m.group(2))),
            "fr": int(float(m.group(3))),
            "rl": int(float(m.group(4))),
            "rr": int(float(m.group(5))),
            "flv": float(m.group(6)),
            "frv": float(m.group(7)),
            "rlv": float(m.group(8)),
            "rrv": float(m.group(9)),
            "lin": float(m.group(10)),
            "ang": float(m.group(11)),
            "theta": float(m.group(12)),
            "dlin": float(m.group(13)),
            "dang": float(m.group(14)),
        }
        print_table()
        return

    # Command feedbacks
    if "Set linear" in line or "[CMD OK]" in line:
        LAST_CMD = line
        print_table()
        return
    if "[CMD REJECT]" in line or "Unrecognized command" in line:
        LAST_CMD = line
        print_table()
        return

    # Sent commands or other
    if "→ SENT" in line:
        LAST_MSG = line
        print_table()
        return

    # Any other message
    if line.strip():
        LAST_MSG = line
        print_table()

def reader_thread(ser, running):
    while running[0]:
        try:
            line = ser.readline()
            if line:
                try:
                    decoded = line.decode(errors='replace').strip()
                except Exception:
                    decoded = repr(line)
                print_pretty(decoded)
        except Exception as e:
            print(f"Reader error: {e}")
            break



def wait_and_heartbeat(ser, lin, ang, seconds):
    # Repeatedly send twist every 100ms
    end_time = time.time() + seconds
    while time.time() < end_time:
        send_twist(ser, lin, ang)
        time.sleep(0.1)

def auto_cycle(ser, running):
    while running[0]:
        # 1. Forward
        print("\n→ Auto: Drive straight at 0.30 m/s")
        wait_and_heartbeat(ser, 0.80, 0.00, 5)
        wait_and_heartbeat(ser, 0, 0.00, 1)
        # 2. Rotate
        print("\n→ Auto: Rotate at +1.57 rad/s (≈90°/s)")
        wait_and_heartbeat(ser, 0.00, 1.57, 5)
        wait_and_heartbeat(ser, 0.00, 0.00, 1)
        wait_secs(1)

        # 3. Curve
        print("\n→ Auto: Curve at 0.20 m/s & 0.50 rad/s")
        wait_and_heartbeat(ser, 0.90, 0.50, 5)
        wait_and_heartbeat(ser, 0.0, 0.0, 1)
        wait_secs(2)

def main():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=0.1)
    except Exception as e:
        print(f"ERROR: Could not open {SERIAL_PORT} at {BAUDRATE} baud: {e}")
        sys.exit(1)

    running = [True]
    rx = threading.Thread(target=reader_thread, args=(ser, running), daemon=True)
    rx.start()

    print(f"\nOpened serial on {SERIAL_PORT} @ {BAUDRATE} baud.\n")
    print("Auto-cycling through drive, rotate, curve... (Ctrl+C to exit)")

    try:
        auto_cycle(ser, running)
    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received. Stopping...")
    finally:
        running[0] = False
        send_twist(ser, 0.00, 0.00)
        ser.close()
        print("Serial closed. Goodbye!")

if __name__ == '__main__':
    main()
