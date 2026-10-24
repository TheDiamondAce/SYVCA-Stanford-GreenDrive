import pygame
import socket
import json
import time

# =========================
# CAR SETTINGS
# =========================
CAR_IP = "192.168.4.1"
CAR_PORT = 100

MAX_SPEED = 100
UPDATE_RATE = 0.05

# Steering sensitivity.
# Since your G920 reaches -1/+1 after ~90 degrees,
# this gives you useful steering without trying to fix
# the physical calibration tonight.
STEERING_GAIN = 0.85

# =========================
# INITIALIZE G920
# =========================
pygame.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("❌ No G920 detected.")
    quit()

wheel = pygame.joystick.Joystick(0)
wheel.init()

print("🎮 Controller:", wheel.get_name())
print("Axes:", wheel.get_numaxes())
print("Buttons:", wheel.get_numbuttons())

# =========================
# CONNECT TO CAR
# =========================
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(3)

print(f"Connecting to {CAR_IP}:{CAR_PORT}...")

try:
    sock.connect((CAR_IP, CAR_PORT))
except Exception as e:
    print("❌ Could not connect to car:")
    print(e)
    pygame.quit()
    quit()

print("🚗 CONNECTED TO ELEGOO!")
print()
print("Controls:")
print("  Steering wheel = steering")
print("  Accelerator    = forward")
print("  Brake          = stop/reduce throttle")
print("  Ctrl+C         = emergency stop")
print()

# =========================
# MOTOR COMMAND
# =========================
def send_motor(left, right):
    left = max(0, min(255, int(left)))
    right = max(0, min(255, int(right)))

    command = {
        "N": 4,
        "H": "G920",
        "D1": left,
        "D2": right
    }

    try:
        sock.sendall(json.dumps(command).encode())
    except Exception as e:
        print("\n❌ Connection error:", e)


def stop_car():
    send_motor(0, 0)


# =========================
# MAIN LOOP
# =========================
try:
    while True:
        pygame.event.pump()

        # -------------------------
        # G920 INPUT
        # -------------------------

        # Axis 0 = steering
        steering = wheel.get_axis(0)

        # Axis 2 = accelerator
        accelerator_raw = wheel.get_axis(2)

        # Logitech pedals commonly report:
        # released  = +1
        # pressed   = -1
        throttle = (1.0 - accelerator_raw) / 2.0
        throttle = max(0.0, min(1.0, throttle))

        # -------------------------
        # DIFFERENTIAL STEERING
        # -------------------------

        base_speed = throttle * MAX_SPEED

        steering_effect = steering * STEERING_GAIN

        left_speed = base_speed * (1 - steering_effect)
        right_speed = base_speed * (1 + steering_effect)

        # Don't allow negative motor speeds.
        # This keeps the demo simple and predictable.
        left_speed = max(0, min(255, left_speed))
        right_speed = max(0, min(255, right_speed))

        # -------------------------
        # SEND TO CAR
        # -------------------------

        send_motor(left_speed, right_speed)

        print(
            f"\r"
            f"Steer: {steering:+.2f} | "
            f"Throttle: {throttle:.2f} | "
            f"L: {left_speed:3.0f} | "
            f"R: {right_speed:3.0f}",
            end=""
        )

        time.sleep(UPDATE_RATE)

except KeyboardInterrupt:
    print("\n\n🛑 Stopping car...")

finally:
    stop_car()
    time.sleep(0.1)
    sock.close()
    pygame.quit()

    print("🚗 Car stopped.")