#!/usr/bin/env python3
import serial
import threading
import time
import sys
import os

# ======= CONFIG =======
SERIAL_PORT = '/dev/ttyUSB0'
BAUDRATE = 115200
SEND_PERIOD = 0.15  # seconds

LIN_STEP = 0.05
ANG_STEP = 0.15
LIN_MAX = 5.0
ANG_MAX = 2.0

DEBUG = False  # Set to True for RX printout

if os.name == 'nt':
    import msvcrt
    def poll_key():
        if msvcrt.kbhit():
            return msvcrt.getch().decode('utf-8').lower()
        else:
            return None
else:
    import select
    import tty
    import termios
    import atexit

    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    atexit.register(lambda: termios.tcsetattr(fd, termios.TCSADRAIN, old_settings))

    def poll_key():
        dr, _, _ = select.select([sys.stdin], [], [], 0)
        if dr:
            return sys.stdin.read(1).lower()
        return None

def clamp(x, mn, mx):
    return max(mn, min(x, mx))

def clear_screen():
    if sys.stdout.isatty():
        print("\033c", end='')

def print_table(ctrl, robot):
    clear_screen()
    print("╔═════════════════════════════ TELEOP & TELEMETRY ═══════════════════════════╗")
    print("║   [Controls: W/S=forward/back | A/D=left/right | Q/E=rot | Spc=stop]      ║")
    print("╠════════════════════════╦════════════════════════╦══════════════════════════╣")
    print("║      CONTROL CMD       ║   ROBOT FEEDBACK      ║     NOTES                ║")
    print("╠════════════════════════╬════════════════════════╬══════════════════════════╣")
    print("║ Lin: {:6.2f} m/s        ║ Lin: {:6.2f} m/s        ║                        ║".format(
        ctrl['lin'], robot['lin']))
    print("║ Ang: {:6.2f} rad/s      ║ Ang: {:6.2f} rad/s      ║                        ║".format(
        ctrl['ang'], robot['ang']))
    print("║ Mode: {:14s} ║ θ: {:9.1f}°         ║                        ║".format(
        ctrl['mode'], robot['theta']))
    print("╚════════════════════════╩════════════════════════╩══════════════════════════╝")

def parse_robot_feedback(line, robot):
    if line.startswith('<S,'):
        # Remove <S, and >
        line = line.strip('<>').lstrip('S,')
        fields = line.split(',')

        try:
            lin_vel = float(fields[5])
            ang_vel = float(fields[9])
            theta = float(fields[12])
            robot['lin'] = lin_vel
            robot['ang'] = ang_vel
            robot['theta'] = theta
        except Exception as e:
            if DEBUG:
                print(f"Parse error: {e} for line {line}")

def reader_thread(ser, running, robot):
    while running[0]:
        try:
            line = ser.readline()
            if line:
                decoded = line.decode(errors='replace').strip()
                if DEBUG:
                    print(f"DEBUG RX: {decoded}")
                parse_robot_feedback(decoded, robot)
        except Exception as e:
            print(f"Reader error: {e}")
            break

def send_twist(ser, lin, ang):
    frame = f'<V,{lin:.2f},{ang:.2f}>\n'
    ser.write(frame.encode())

def teleop_loop(ser, running):
    lin = 0.0
    ang = 0.0
    mode = "Stopped"
    robot = {'lin': 0.0, 'ang': 0.0, 'theta': 0.0}

    rx = threading.Thread(target=reader_thread, args=(ser, running, robot), daemon=True)
    rx.start()

    print_table({'lin': lin, 'ang': ang, 'mode': mode}, robot)

    try:
        while running[0]:
            key = poll_key()
            if key:
                if key == '\x03' or key == '\x1b':  # Ctrl+C or ESC
                    print("\nExiting teleop.")
                    break
                elif key == 'w':
                    lin = clamp(lin + LIN_STEP, -LIN_MAX, LIN_MAX)
                    mode = "Forward"
                elif key == 's':
                    lin = clamp(lin - LIN_STEP, -LIN_MAX, LIN_MAX)
                    mode = "Backward"
                elif key == 'a':
                    ang = clamp(ang + ANG_STEP, -ANG_MAX, ANG_MAX)
                    mode = "Left"
                elif key == 'd':
                    ang = clamp(ang - ANG_STEP, -ANG_MAX, ANG_MAX)
                    mode = "Right"
                elif key == 'q':
                    lin = 0.0
                    ang = clamp(ang + ANG_STEP, -ANG_MAX, ANG_MAX)
                    mode = "Rotate Left"
                elif key == 'e':
                    lin = 0.0
                    ang = clamp(ang - ANG_STEP, -ANG_MAX, ANG_MAX)
                    mode = "Rotate Right"
                elif key == ' ':
                    lin = 0.0
                    ang = 0.0
                    mode = "Stopped"
            # Heartbeat: send current command every cycle!
            send_twist(ser, lin, ang)
            print_table({'lin': lin, 'ang': ang, 'mode': mode}, robot)
            time.sleep(SEND_PERIOD)

    except KeyboardInterrupt:
        print("\nKeyboardInterrupt received. Stopping...")
    finally:
        running[0] = False
        send_twist(ser, 0.00, 0.00)
        ser.close()
        print("Serial closed. Goodbye!")

def main():
    try:
        ser = serial.Serial(SERIAL_PORT, BAUDRATE, timeout=0.1)
    except Exception as e:
        print(f"ERROR: Could not open {SERIAL_PORT} at {BAUDRATE} baud: {e}")
        sys.exit(1)

    running = [True]
    teleop_loop(ser, running)

if __name__ == '__main__':
    main()
