import pygame
import socket
import json
import time

# =========================
# CAR
# =========================
CAR_IP = "192.168.4.1"
CAR_PORT = 100

MAX_SPEED = 100
UPDATE_RATE = 0.05

# Steering
STEERING_GAIN = 0.85

# =========================
# PHYSICS
# =========================
# How quickly the car reaches requested throttle speed
ACCELERATION = 180.0

# Natural slowdown when accelerator is released
FRICTION = 45.0

# Brake pedal slowdown
BRAKE_DECELERATION = 220.0

# =========================
# G920
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
# WIFI
# =========================
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(3)

print(f"Connecting to {CAR_IP}:{CAR_PORT}...")

try:
    sock.connect((CAR_IP, CAR_PORT))
except Exception as e:
    print("❌ Could not connect:")
    print(e)
    pygame.quit()
    quit()

print("🚗 CONNECTED TO ELEGOO!")
print()
print("Controls:")
print("  Wheel      = steering")
print("  Accelerator = throttle")
print("  Brake       = braking")
print("  Ctrl+C     = emergency stop")
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
# SIMULATED VEHICLE SPEED
# =========================

vehicle_speed = 0.0

last_time = time.monotonic()


# =========================
# MAIN LOOP
# =========================

try:

    while True:

        pygame.event.pump()

        now = time.monotonic()
        dt = now - last_time
        last_time = now

        # Keep physics stable
        dt = min(dt, 0.1)

        # -------------------------
        # STEERING
        # -------------------------

        # NEGATIVE fixes reversed steering
        steering = -wheel.get_axis(0)

        steering = max(-1.0, min(1.0, steering))


        # -------------------------
        # ACCELERATOR
        # -------------------------

        accelerator_raw = wheel.get_axis(2)

        throttle = (1.0 - accelerator_raw) / 2.0
        throttle = max(0.0, min(1.0, throttle))


        # -------------------------
        # BRAKE
        # -------------------------

        # Axis 3 = brake
        brake_raw = wheel.get_axis(3)

        brake = (1.0 - brake_raw) / 2.0
        brake = max(0.0, min(1.0, brake))


        # -------------------------
        # TARGET SPEED
        # -------------------------

        target_speed = throttle * MAX_SPEED


        # -------------------------
        # ACCELERATION / FRICTION
        # -------------------------

        if throttle > 0.01:

            # Accelerate toward target
            if vehicle_speed < target_speed:

                vehicle_speed += ACCELERATION * dt

                vehicle_speed = min(
                    vehicle_speed,
                    target_speed
                )

            else:

                # Slowly settle toward target
                vehicle_speed -= ACCELERATION * 0.5 * dt

                vehicle_speed = max(
                    vehicle_speed,
                    target_speed
                )

        else:

            # Accelerator released:
            # simulate rolling resistance
            vehicle_speed -= FRICTION * dt

            vehicle_speed = max(
                0,
                vehicle_speed
            )


        # -------------------------
        # BRAKING
        # -------------------------

        if brake > 0.05:

            vehicle_speed -= (
                BRAKE_DECELERATION
                * brake
                * dt
            )

            vehicle_speed = max(
                0,
                vehicle_speed
            )


        # -------------------------
        # DIFFERENTIAL STEERING
        # -------------------------

        steering_effect = steering * STEERING_GAIN

        left_speed = vehicle_speed * (
            1 - steering_effect
        )

        right_speed = vehicle_speed * (
            1 + steering_effect
        )


        # -------------------------
        # LIMIT MOTORS
        # -------------------------

        left_speed = max(
            0,
            min(255, left_speed)
        )

        right_speed = max(
            0,
            min(255, right_speed)
        )


        # -------------------------
        # SEND
        # -------------------------

        send_motor(
            left_speed,
            right_speed
        )


        print(
            f"\r"
            f"Steer: {steering:+.2f} | "
            f"Throttle: {throttle:.2f} | "
            f"Brake: {brake:.2f} | "
            f"Speed: {vehicle_speed:5.1f} | "
            f"L: {left_speed:3.0f} | "
            f"R: {right_speed:3.0f}",
            end=""
        )


        time.sleep(UPDATE_RATE)


except KeyboardInterrupt:

    print("\n\n🛑 Stopping...")


finally:

    stop_car()

    time.sleep(0.1)

    sock.close()

    pygame.quit()

    print("🚗 Car stopped.")
