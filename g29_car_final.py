import pygame
import socket
import json
import time

# ============================================================
# DRIVE SENSE
# ELEGOO Smart Robot Car V4.0 + Logitech G29
# ============================================================

CAR_IP = "192.168.4.1"
CAR_PORT = 100

MAX_SPEED = 100
UPDATE_RATE = 0.05

# Steering
STEERING_GAIN = 0.85

# ============================================================
# VEHICLE PHYSICS
# ============================================================

ACCELERATION = 180.0
FRICTION = 45.0
BRAKE_DECELERATION = 220.0

vehicle_speed = 0.0

# ============================================================
# GEAR STATES
# ============================================================

PARK = "P"
REVERSE = "R"
NEUTRAL = "N"
DRIVE = "D"

gear = PARK

# Conventional G29 pygame button mapping
#
# 0 = X / Cross
# 1 = Circle
# 2 = Square
# 3 = Triangle

BUTTON_X = 0
BUTTON_CIRCLE = 1
BUTTON_SQUARE = 2
BUTTON_TRIANGLE = 3

# ============================================================
# COLORS
# ============================================================

BG = (12, 15, 20)
PANEL = (22, 27, 35)
PANEL_2 = (28, 34, 43)
TEXT = (235, 240, 245)
MUTED = (145, 155, 165)
GREEN = (60, 220, 130)
YELLOW = (240, 200, 70)
RED = (240, 80, 80)
BLUE = (80, 170, 255)

# ============================================================
# PYGAME
# ============================================================

pygame.init()
pygame.font.init()
pygame.joystick.init()

if pygame.joystick.get_count() == 0:
    print("❌ No G29 detected.")
    pygame.quit()
    quit()

wheel = pygame.joystick.Joystick(0)
wheel.init()

print("=" * 60)
print("DRIVE SENSE")
print("=" * 60)
print("Controller:", wheel.get_name())
print("Axes:", wheel.get_numaxes())
print("Buttons:", wheel.get_numbuttons())
print()

# ============================================================
# WIFI
# ============================================================

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
print("Gears:")
print("  TRIANGLE = DRIVE")
print("  SQUARE   = REVERSE")
print("  CIRCLE   = NEUTRAL")
print("  X        = PARK")
print()
print("Wheel = steering")
print("Accelerator = throttle")
print("Brake = braking")
print("ESC = emergency stop")
print()

# ============================================================
# MOTOR COMMAND
# ============================================================

def send_motor(left, right):

    left = max(0, min(255, int(left)))
    right = max(0, min(255, int(right)))

    command = {
        "N": 4,
        "H": "G29",
        "D1": left,
        "D2": right
    }

    try:
        sock.sendall(json.dumps(command).encode())
    except Exception as e:
        print("\n❌ Connection error:", e)


def stop_car():

    global vehicle_speed

    vehicle_speed = 0

    send_motor(0, 0)


# ============================================================
# GEAR BUTTON HANDLING
# ============================================================

previous_buttons = [False] * wheel.get_numbuttons()


def process_gear_buttons():

    global gear

    current_buttons = [
        wheel.get_button(i)
        for i in range(wheel.get_numbuttons())
    ]

    def pressed(button):
        if button >= len(current_buttons):
            return False

        return (
            current_buttons[button]
            and not previous_buttons[button]
        )

    if pressed(BUTTON_TRIANGLE):
        gear = DRIVE

    elif pressed(BUTTON_SQUARE):
        gear = REVERSE

    elif pressed(BUTTON_CIRCLE):
        gear = NEUTRAL

    elif pressed(BUTTON_X):
        gear = PARK

    for i in range(len(current_buttons)):
        previous_buttons[i] = current_buttons[i]


# ============================================================
# PEDALS
# ============================================================

def get_throttle():

    raw = wheel.get_axis(2)

    throttle = (1.0 - raw) / 2.0

    return max(0.0, min(1.0, throttle))


def get_brake():

    raw = wheel.get_axis(3)

    brake = (1.0 - raw) / 2.0

    return max(0.0, min(1.0, brake))


# ============================================================
# HUD
# ============================================================

screen = pygame.display.set_mode((1100, 700))
pygame.display.set_caption("DriveSense — ELEGOO V4.0")

clock = pygame.time.Clock()

font_title = pygame.font.Font(None, 46)
font_large = pygame.font.Font(None, 72)
font_medium = pygame.font.Font(None, 38)
font_small = pygame.font.Font(None, 26)
font_tiny = pygame.font.Font(None, 21)


def draw_text(text, x, y, font, color=TEXT):

    surface = font.render(str(text), True, color)
    screen.blit(surface, (x, y))


def panel(x, y, w, h):

    pygame.draw.rect(
        screen,
        PANEL,
        (x, y, w, h),
        border_radius=14
    )


def bar(x, y, w, h, value, color):

    pygame.draw.rect(
        screen,
        PANEL_2,
        (x, y, w, h),
        border_radius=6
    )

    fill = int(w * max(0.0, min(1.0, value)))

    if fill > 0:
        pygame.draw.rect(
            screen,
            color,
            (x, y, fill, h),
            border_radius=6
        )


def draw_hud(
    steering,
    throttle,
    brake,
    left_speed,
    right_speed
):

    screen.fill(BG)

    # ========================================================
    # HEADER
    # ========================================================

    draw_text(
        "DRIVE SENSE",
        40,
        28,
        font_title
    )

    draw_text(
        "ELEGOO SMART ROBOT CAR V4.0",
        42,
        70,
        font_small,
        MUTED
    )

    # Connection indicator

    pygame.draw.circle(
        screen,
        GREEN,
        (1015, 48),
        8
    )

    draw_text(
        "CONNECTED",
        850,
        36,
        font_small,
        GREEN
    )

    # ========================================================
    # SPEED
    # ========================================================

    panel(40, 115, 330, 220)

    draw_text(
        "VEHICLE SPEED",
        65,
        140,
        font_small,
        MUTED
    )

    draw_text(
        f"{vehicle_speed:04.1f}",
        65,
        170,
        font_large
    )

    draw_text(
        "SIMULATED km/h",
        68,
        255,
        font_small,
        MUTED
    )

    # ========================================================
    # GEAR
    # ========================================================

    panel(395, 115, 200, 220)

    draw_text(
        "GEAR",
        425,
        140,
        font_small,
        MUTED
    )

    gear_color = {
        PARK: RED,
        REVERSE: YELLOW,
        NEUTRAL: MUTED,
        DRIVE: GREEN
    }.get(gear, TEXT)

    draw_text(
        gear,
        465,
        175,
        font_large,
        gear_color
    )

    labels = {
        PARK: "PARK",
        REVERSE: "REVERSE",
        NEUTRAL: "NEUTRAL",
        DRIVE: "DRIVE"
    }

    draw_text(
        labels.get(gear, ""),
        425,
        255,
        font_small,
        gear_color
    )

    # ========================================================
    # INPUTS
    # ========================================================

    panel(620, 115, 440, 220)

    draw_text(
        "DRIVER INPUT",
        650,
        140,
        font_small,
        MUTED
    )

    draw_text(
        f"STEERING  {steering:+.2f}",
        650,
        180,
        font_medium
    )

    bar(
        650,
        220,
        350,
        18,
        (steering + 1) / 2,
        BLUE
    )

    draw_text(
        f"THROTTLE  {throttle * 100:3.0f}%",
        650,
        255,
        font_small
    )

    bar(
        800,
        255,
        200,
        14,
        throttle,
        GREEN
    )

    draw_text(
        f"BRAKE  {brake * 100:3.0f}%",
        650,
        285,
        font_small
    )

    bar(
        800,
        285,
        200,
        14,
        brake,
        RED
    )

    # ========================================================
    # MOTOR OUTPUT
    # ========================================================

    panel(40, 360, 555, 260)

    draw_text(
        "MOTOR OUTPUT",
        65,
        385,
        font_small,
        MUTED
    )

    draw_text(
        f"LEFT   {left_speed:3.0f}",
        70,
        430,
        font_medium
    )

    bar(
        260,
        440,
        270,
        20,
        left_speed / 255,
        BLUE
    )

    draw_text(
        f"RIGHT  {right_speed:3.0f}",
        70,
        490,
        font_medium
    )

    bar(
        260,
        500,
        270,
        20,
        right_speed / 255,
        BLUE
    )

    draw_text(
        "Differential drive control",
        70,
        555,
        font_small,
        MUTED
    )

    # ========================================================
    # SENSOR / SYSTEM PANEL
    # ========================================================

    panel(620, 360, 440, 260)

    draw_text(
        "ROBOT TELEMETRY",
        650,
        385,
        font_small,
        MUTED
    )

    draw_text(
        "MPU6050 IMU",
        650,
        430,
        font_medium
    )

    draw_text(
        "INTERNAL",
        890,
        432,
        font_small,
        YELLOW
    )

    draw_text(
        "Stock V4 firmware does not stream",
        650,
        475,
        font_tiny,
        MUTED
    )

    draw_text(
        "MPU6050 values through the Wi-Fi API.",
        650,
        500,
        font_tiny,
        MUTED
    )

    draw_text(
        "Wi-Fi",
        650,
        550,
        font_small,
        MUTED
    )

    draw_text(
        "192.168.4.1",
        760,
        550,
        font_small,
        GREEN
    )

    draw_text(
        "TCP",
        650,
        580,
        font_small,
        MUTED
    )

    draw_text(
        "PORT 100",
        760,
        580,
        font_small,
        GREEN
    )

    # ========================================================
    # FOOTER
    # ========================================================

    draw_text(
        "△ DRIVE   □ REVERSE   ○ NEUTRAL   ✕ PARK",
        40,
        655,
        font_small,
        MUTED
    )

    pygame.display.flip()


# ============================================================
# MAIN LOOP
# ============================================================

last_time = time.monotonic()

try:

    while True:

        # ----------------------------------------------------
        # EVENTS
        # ----------------------------------------------------

        for event in pygame.event.get():

            if event.type == pygame.QUIT:

                raise KeyboardInterrupt

            if event.type == pygame.KEYDOWN:

                if event.key == pygame.K_ESCAPE:

                    gear = PARK
                    vehicle_speed = 0

                    raise KeyboardInterrupt

        pygame.event.pump()

        # ----------------------------------------------------
        # TIMING
        # ----------------------------------------------------

        now = time.monotonic()

        dt = now - last_time

        last_time = now

        dt = min(dt, 0.1)

        # ----------------------------------------------------
        # GEAR
        # ----------------------------------------------------

        process_gear_buttons()

        # ----------------------------------------------------
        # STEERING
        # ----------------------------------------------------

        steering = -wheel.get_axis(0)

        steering = max(
            -1.0,
            min(1.0, steering)
        )

        # ----------------------------------------------------
        # THROTTLE
        # ----------------------------------------------------

        throttle = get_throttle()

        # ----------------------------------------------------
        # BRAKE
        # ----------------------------------------------------

        brake = get_brake()

        # ----------------------------------------------------
        # VEHICLE PHYSICS
        # ----------------------------------------------------

        if gear == DRIVE:

            target_speed = throttle * MAX_SPEED

        elif gear == REVERSE:

            target_speed = throttle * MAX_SPEED

        else:

            target_speed = 0

        # Accelerate

        if vehicle_speed < target_speed:

            vehicle_speed += (
                ACCELERATION * dt
            )

            vehicle_speed = min(
                vehicle_speed,
                target_speed
            )

        # Release accelerator

        elif throttle <= 0.01:

            vehicle_speed -= (
                FRICTION * dt
            )

            vehicle_speed = max(
                0,
                vehicle_speed
            )

        # Settle toward lower target

        else:

            vehicle_speed -= (
                ACCELERATION * 0.5 * dt
            )

            vehicle_speed = max(
                vehicle_speed,
                target_speed
            )

        # ----------------------------------------------------
        # BRAKING
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # PARK / NEUTRAL
        # ----------------------------------------------------

        if gear in [PARK, NEUTRAL]:

            vehicle_speed = max(
                0,
                vehicle_speed - FRICTION * dt
            )

            left_speed = 0
            right_speed = 0

        else:

            # ------------------------------------------------
            # DIFFERENTIAL STEERING
            # ------------------------------------------------

            steering_effect = (
                steering * STEERING_GAIN
            )

            left_speed = vehicle_speed * (
                1 - steering_effect
            )

            right_speed = vehicle_speed * (
                1 + steering_effect
            )

            # ------------------------------------------------
            # BRAKE
            # ------------------------------------------------

            if brake > 0.05:

                brake_factor = max(
                    0,
                    1.0 - brake
                )

                left_speed *= brake_factor
                right_speed *= brake_factor

            left_speed = max(
                0,
                min(255, left_speed)
            )

            right_speed = max(
                0,
                min(255, right_speed)
            )

        # ----------------------------------------------------
        # SEND MOTOR COMMAND
        # ----------------------------------------------------

        send_motor(
            left_speed,
            right_speed
        )

        # ----------------------------------------------------
        # HUD
        # ----------------------------------------------------

        draw_hud(
            steering,
            throttle,
            brake,
            left_speed,
            right_speed
        )

        # ----------------------------------------------------
        # LOOP
        # ----------------------------------------------------

        clock.tick(
            int(1 / UPDATE_RATE)
        )


except KeyboardInterrupt:

    print("\n\n🛑 Stopping...")


finally:

    stop_car()

    time.sleep(0.1)

    sock.close()

    pygame.quit()

    print("🚗 Car stopped.")