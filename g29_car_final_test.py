import pygame
import socket
import json
import time
import select
import re

# ============================================================
# CONFIG
# ============================================================

CAR_IP = "192.168.4.1"
CAR_PORT = 100

LOOP_HZ = 20

# Motor limits
ECO_MAX = 130
SPORT_MAX = 190
REVERSE_MAX = 110

# Acceleration
ECO_ACCEL = 105.0
SPORT_ACCEL = 260.0

FRICTION = 45.0
BRAKE_DECEL = 260.0

STEERING_GAIN = 0.85

# Ultrasonic safety
SENSOR_INTERVAL = 0.25
EMERGENCY_DISTANCE = 20.0
RESET_DISTANCE = 50.0

# Simulation
ROBOT_LENGTH_M = 0.263
REAL_CAR_LENGTH_M = 4.50
MODEL_SCALE = REAL_CAR_LENGTH_M / ROBOT_LENGTH_M
ROBOT_MAX_MPS = 0.75

# ============================================================
# STATES
# ============================================================

PARK = "P"
REVERSE = "R"
NEUTRAL = "N"
DRIVE = "D"

ECO = "ECO"
SPORT = "SPORT"

gear = PARK
mode = ECO

speed = 0.0

ultrasonic_cm = None
emergency_lock = False

last_sensor_time = 0
sensor_id = 0

# Cache motor commands
last_left = -1
last_right = -1
last_reverse = None

# ============================================================
# G29 BUTTONS
# ============================================================

BUTTON_X = 0
BUTTON_CIRCLE = 1
BUTTON_SQUARE = 2
BUTTON_TRIANGLE = 3

# ============================================================
# COLORS
# ============================================================

BG = (12, 15, 20)
PANEL = (22, 27, 35)
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
    print("ERROR: G29 not detected.")
    pygame.quit()
    raise SystemExit

wheel = pygame.joystick.Joystick(0)
wheel.init()

print("=" * 55)
print("DRIVE SENSE")
print("=" * 55)
print("Controller:", wheel.get_name())
print("Axes:", wheel.get_numaxes())
print("Buttons:", wheel.get_numbuttons())
print()
print("Triangle = DRIVE")
print("Square   = REVERSE")
print("Circle   = NEUTRAL")
print("X        = PARK")
print()
print("E = ECO")
print("S = SPORT")
print("ESC = STOP")
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
    print("ERROR:", e)
    pygame.quit()
    raise SystemExit

print("CONNECTED TO ELEGOO")
print()

# ============================================================
# MOTOR CONTROL
# ============================================================

def send_motor(left, right, reverse=False, force=False):
    """
    Send motor commands to the ELEGOO V4.

    Forward:
        N=4 controls left/right speeds.

    Reverse:
        N=1 explicitly sets motor direction.
        D3=1 -> forward
        D3=2 -> reverse
        D3=0 -> stop
    """

    global last_left
    global last_right
    global last_reverse

    left = int(max(0, min(255, left)))
    right = int(max(0, min(255, right)))

    # Don't resend identical commands unless forced
    if (
        not force
        and left == last_left
        and right == last_right
        and reverse == last_reverse
    ):
        return

    try:

        # ----------------------------------------------------
        # REVERSE
        # ----------------------------------------------------

        if reverse:

            # ELEGOO V4:
            # D1 = motor
            # D2 = speed
            # D3 = direction
            #
            # D3 = 2 means REVERSE

            left_command = {
                "N": 1,
                "H": "G29L",
                "D1": 1,
                "D2": left,
                "D3": 2
            }

            right_command = {
                "N": 1,
                "H": "G29R",
                "D1": 2,
                "D2": right,
                "D3": 2
            }

            sock.sendall(
                json.dumps(left_command).encode()
            )

            sock.sendall(
                json.dumps(right_command).encode()
            )

        # ----------------------------------------------------
        # FORWARD / NORMAL
        # ----------------------------------------------------

        else:

            command = {
                "N": 4,
                "H": "G29",
                "D1": left,
                "D2": right
            }

            sock.sendall(
                json.dumps(command).encode()
            )

        last_left = left
        last_right = right
        last_reverse = reverse

    except Exception as e:
        print("Motor error:", e)


def stop():
    """
    Force a real stop command.
    """

    global speed
    global last_left
    global last_right
    global last_reverse

    speed = 0

    try:

        # Explicitly stop ALL motors.
        #
        # ELEGOO V4:
        # N=1
        # D1=0 -> all motors
        # D2=0 -> speed 0
        # D3=0 -> stop

        command = {
            "N": 1,
            "H": "STOP",
            "D1": 0,
            "D2": 0,
            "D3": 0
        }

        sock.sendall(
            json.dumps(command).encode()
        )

    except Exception as e:
        print("Stop error:", e)

    # Reset cache so next command is definitely transmitted
    last_left = -1
    last_right = -1
    last_reverse = None


# ============================================================
# ULTRASONIC
# ============================================================

def request_sensor():

    global last_sensor_time
    global sensor_id

    now = time.monotonic()

    if now - last_sensor_time < SENSOR_INTERVAL:
        return

    last_sensor_time = now
    sensor_id += 1

    command = {
        "N": 21,
        "H": f"US{sensor_id}",
        "D1": 2
    }

    try:

        sock.sendall(
            json.dumps(command).encode()
        )

    except Exception:
        pass


def read_sensor():

    global ultrasonic_cm

    try:

        ready, _, _ = select.select(
            [sock],
            [],
            [],
            0
        )

        if not ready:
            return

        data = sock.recv(4096)

        if not data:
            return

        text = data.decode(
            "utf-8",
            errors="ignore"
        )

        values = re.findall(
            r"US\d+_(-?\d+(?:\.\d+)?)",
            text
        )

        if values:
            ultrasonic_cm = float(
                values[-1]
            )

    except Exception:
        pass


# ============================================================
# SAFETY
# ============================================================

def safety_check():

    global emergency_lock
    global gear
    global speed

    if ultrasonic_cm is None:
        return

    # --------------------------------------------------------
    # EMERGENCY BRAKE
    # --------------------------------------------------------

    if (
        gear == DRIVE
        and ultrasonic_cm <= EMERGENCY_DISTANCE
        and not emergency_lock
    ):

        emergency_lock = True
        gear = NEUTRAL
        speed = 0

        # Force stop so cache cannot prevent it
        stop()

        print()
        print("!!! EMERGENCY BRAKE !!!")
        print(
            f"Obstacle: {ultrasonic_cm:.1f} cm"
        )
        print("DRIVE LOCKED")
        print()

    # --------------------------------------------------------
    # SAFETY RESET
    # --------------------------------------------------------

    if (
        emergency_lock
        and ultrasonic_cm >= RESET_DISTANCE
    ):

        emergency_lock = False

        print("Safety distance restored.")
        print("DRIVE UNLOCKED.")


# ============================================================
# INPUT
# ============================================================

previous_buttons = [
    False
] * wheel.get_numbuttons()


def button_pressed(button, current):

    return (
        current[button]
        and not previous_buttons[button]
    )


def read_inputs():

    global gear
    global mode

    current = [
        wheel.get_button(i)
        for i in range(
            wheel.get_numbuttons()
        )
    ]

    # --------------------------------------------------------
    # GEAR BUTTONS
    # --------------------------------------------------------

    if button_pressed(
        BUTTON_TRIANGLE,
        current
    ):

        if not emergency_lock:
            gear = DRIVE
        else:
            print(
                "Drive locked by safety system."
            )

    elif button_pressed(
        BUTTON_SQUARE,
        current
    ):

        gear = REVERSE

    elif button_pressed(
        BUTTON_CIRCLE,
        current
    ):

        gear = NEUTRAL

    elif button_pressed(
        BUTTON_X,
        current
    ):

        gear = PARK

    # Save button state
    for i in range(len(current)):
        previous_buttons[i] = current[i]

    # --------------------------------------------------------
    # KEYBOARD MODES
    # --------------------------------------------------------

    keys = pygame.key.get_pressed()

    if keys[pygame.K_e]:

        mode = ECO

    elif keys[pygame.K_s]:

        mode = SPORT


# ============================================================
# PEDALS
# ============================================================

def throttle():

    raw = wheel.get_axis(2)

    return max(
        0,
        min(
            1,
            (1 - raw) / 2
        )
    )


def brake():

    raw = wheel.get_axis(3)

    return max(
        0,
        min(
            1,
            (1 - raw) / 2
        )
    )


# ============================================================
# VEHICLE PHYSICS
# ============================================================

def update_physics(
    dt,
    gas,
    brake_input
):

    global speed

    if mode == ECO:

        max_speed = ECO_MAX
        acceleration = ECO_ACCEL

    else:

        max_speed = SPORT_MAX
        acceleration = SPORT_ACCEL

    # --------------------------------------------------------
    # TARGET SPEED
    # --------------------------------------------------------

    if gear == REVERSE:

        target = gas * min(
            REVERSE_MAX,
            max_speed
        )

    elif gear == DRIVE:

        target = gas * max_speed

    else:

        target = 0

    # --------------------------------------------------------
    # ACCELERATION
    # --------------------------------------------------------

    if speed < target:

        speed += (
            acceleration * dt
        )

        speed = min(
            speed,
            target
        )

    # --------------------------------------------------------
    # RELEASE THROTTLE
    # --------------------------------------------------------

    elif gas <= 0.01:

        speed -= (
            FRICTION * dt
        )

        speed = max(
            0,
            speed
        )

    # --------------------------------------------------------
    # SLOW TOWARD TARGET
    # --------------------------------------------------------

    else:

        speed -= (
            acceleration
            * 0.5
            * dt
        )

        speed = max(
            speed,
            target
        )

    # --------------------------------------------------------
    # BRAKE
    # --------------------------------------------------------

    if brake_input > 0.05:

        speed -= (
            BRAKE_DECEL
            * brake_input
            * dt
        )

        speed = max(
            0,
            speed
        )


# ============================================================
# MOTOR OUTPUT
# ============================================================

def calculate_motors(
    steering,
    brake_input
):

    if gear in (
        PARK,
        NEUTRAL
    ):

        return 0, 0

    effect = (
        steering
        * STEERING_GAIN
    )

    left = (
        speed
        * (1 - effect)
    )

    right = (
        speed
        * (1 + effect)
    )

    # Brake reduces motor output
    if brake_input > 0.05:

        factor = 1 - brake_input

        left *= factor
        right *= factor

    left = max(
        0,
        min(
            255,
            left
        )
    )

    right = max(
        0,
        min(
            255,
            right
        )
    )

    return left, right


# ============================================================
# SIMULATED SPEED
# ============================================================

def simulated_speed():

    max_speed = (
        ECO_MAX
        if mode == ECO
        else SPORT_MAX
    )

    ratio = max(
        0,
        min(
            1,
            speed / max_speed
        )
    )

    robot_mps = (
        ratio
        * ROBOT_MAX_MPS
    )

    full_mps = (
        robot_mps
        * MODEL_SCALE
    )

    if mode == ECO:

        full_mps *= 0.85

    else:

        full_mps *= 1.15

    return (
        full_mps * 3.6,
        full_mps * 2.236936
    )


# ============================================================
# HUD
# ============================================================

screen = pygame.display.set_mode(
    (1100, 700)
)

pygame.display.set_caption(
    "DriveSense — ELEGOO V4.0"
)

clock = pygame.time.Clock()

font_title = pygame.font.Font(
    None,
    46
)

font_big = pygame.font.Font(
    None,
    72
)

font_medium = pygame.font.Font(
    None,
    38
)

font_small = pygame.font.Font(
    None,
    26
)

font_tiny = pygame.font.Font(
    None,
    21
)


def text(
    value,
    x,
    y,
    font,
    color=TEXT
):

    screen.blit(
        font.render(
            str(value),
            True,
            color
        ),
        (x, y)
    )


def draw_panel(
    x,
    y,
    w,
    h
):

    pygame.draw.rect(
        screen,
        PANEL,
        (x, y, w, h),
        border_radius=14
    )


def draw_bar(
    x,
    y,
    w,
    h,
    value,
    color
):

    pygame.draw.rect(
        screen,
        (28, 34, 43),
        (x, y, w, h),
        border_radius=6
    )

    fill = int(
        w
        * max(
            0,
            min(
                1,
                value
            )
        )
    )

    if fill:

        pygame.draw.rect(
            screen,
            color,
            (x, y, fill, h),
            border_radius=6
        )


def draw_hud(
    steering,
    gas,
    brake_input,
    left,
    right
):

    screen.fill(BG)

    kmh, mph = simulated_speed()

    # ========================================================
    # HEADER
    # ========================================================

    text(
        "DRIVE SENSE",
        40,
        28,
        font_title
    )

    text(
        "ELEGOO SMART ROBOT CAR V4.0",
        42,
        70,
        font_small,
        MUTED
    )

    text(
        "CONNECTED",
        850,
        36,
        font_small,
        GREEN
    )

    pygame.draw.circle(
        screen,
        GREEN,
        (1015, 48),
        8
    )

    # ========================================================
    # SPEED
    # ========================================================

    draw_panel(
        40,
        115,
        330,
        220
    )

    text(
        "FULL-SIZE EQUIVALENT",
        65,
        140,
        font_small,
        MUTED
    )

    text(
        f"{kmh:04.1f}",
        65,
        170,
        font_big
    )

    text(
        f"km/h   {mph:04.1f} mph",
        68,
        255,
        font_small,
        MUTED
    )

    text(
        f"MODEL SCALE  1:{MODEL_SCALE:.1f}",
        68,
        285,
        font_tiny,
        BLUE
    )

    # ========================================================
    # GEAR
    # ========================================================

    draw_panel(
        395,
        115,
        200,
        220
    )

    text(
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
    }[gear]

    text(
        gear,
        465,
        175,
        font_big,
        gear_color
    )

    text(
        {
            PARK: "PARK",
            REVERSE: "REVERSE",
            NEUTRAL: "NEUTRAL",
            DRIVE: "DRIVE"
        }[gear],
        425,
        255,
        font_small,
        gear_color
    )

    # ========================================================
    # INPUT
    # ========================================================

    draw_panel(
        620,
        115,
        440,
        220
    )

    text(
        "DRIVER INPUT",
        650,
        140,
        font_small,
        MUTED
    )

    text(
        f"STEERING  {steering:+.2f}",
        650,
        180,
        font_medium
    )

    draw_bar(
        650,
        220,
        350,
        18,
        (steering + 1) / 2,
        BLUE
    )

    text(
        f"THROTTLE  {gas * 100:3.0f}%",
        650,
        255,
        font_small
    )

    draw_bar(
        800,
        255,
        200,
        14,
        gas,
        GREEN
    )

    text(
        f"BRAKE  {brake_input * 100:3.0f}%",
        650,
        285,
        font_small
    )

    draw_bar(
        800,
        285,
        200,
        14,
        brake_input,
        RED
    )

    # ========================================================
    # MOTOR
    # ========================================================

    draw_panel(
        40,
        360,
        555,
        260
    )

    text(
        "MOTOR OUTPUT",
        65,
        385,
        font_small,
        MUTED
    )

    text(
        f"LEFT   {left:3.0f}",
        70,
        430,
        font_medium
    )

    draw_bar(
        260,
        440,
        270,
        20,
        left / 255,
        BLUE
    )

    text(
        f"RIGHT  {right:3.0f}",
        70,
        490,
        font_medium
    )

    draw_bar(
        260,
        500,
        270,
        20,
        right / 255,
        BLUE
    )

    text(
        "Differential drive control",
        70,
        555,
        font_small,
        MUTED
    )

    # ========================================================
    # TELEMETRY
    # ========================================================

    draw_panel(
        620,
        360,
        440,
        260
    )

    text(
        "ROBOT TELEMETRY",
        650,
        385,
        font_small,
        MUTED
    )

    # Ultrasonic
    text(
        "ULTRASONIC",
        650,
        425,
        font_medium
    )

    if ultrasonic_cm is None:

        text(
            "WAITING...",
            850,
            430,
            font_small,
            YELLOW
        )

    else:

        color = (
            RED
            if ultrasonic_cm <= 20
            else YELLOW
            if ultrasonic_cm <= 50
            else GREEN
        )

        text(
            f"{ultrasonic_cm:.1f} cm",
            830,
            428,
            font_medium,
            color
        )

    # Safety
    if emergency_lock:

        text(
            "EMERGENCY BRAKE",
            650,
            470,
            font_small,
            RED
        )

        text(
            "DRIVE LOCKED",
            900,
            470,
            font_tiny,
            RED
        )

    elif (
        ultrasonic_cm is not None
        and ultrasonic_cm <= 50
    ):

        text(
            "CAUTION",
            650,
            470,
            font_small,
            YELLOW
        )

    else:

        text(
            "CLEAR",
            650,
            470,
            font_small,
            GREEN
        )

    # Mode
    text(
        "MODE",
        650,
        515,
        font_small,
        MUTED
    )

    text(
        mode,
        900,
        510,
        font_medium,
        GREEN if mode == ECO else YELLOW
    )

    # Footer
    text(
        "△ DRIVE   □ REVERSE   ○ NEUTRAL   ✕ PARK",
        40,
        655,
        font_small,
        MUTED
    )

    text(
        "E ECO   •   S SPORT",
        800,
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
        # PYGAME EVENTS
        # ----------------------------------------------------

        for event in pygame.event.get():

            if event.type == pygame.QUIT:

                raise KeyboardInterrupt

            if (
                event.type == pygame.KEYDOWN
                and event.key == pygame.K_ESCAPE
            ):

                gear = PARK

                stop()

                raise KeyboardInterrupt

        pygame.event.pump()

        # ----------------------------------------------------
        # TIME
        # ----------------------------------------------------

        now = time.monotonic()

        dt = min(
            now - last_time,
            0.1
        )

        last_time = now

        # ----------------------------------------------------
        # INPUT
        # ----------------------------------------------------

        read_inputs()

        steering = -wheel.get_axis(0)

        steering = max(
            -1,
            min(
                1,
                steering
            )
        )

        gas = throttle()

        brake_input = brake()

        # ----------------------------------------------------
        # SENSOR
        # ----------------------------------------------------

        request_sensor()

        read_sensor()

        safety_check()

        # ----------------------------------------------------
        # PHYSICS
        # ----------------------------------------------------

        update_physics(
            dt,
            gas,
            brake_input
        )

        # ----------------------------------------------------
        # MOTOR
        # ----------------------------------------------------

        left, right = calculate_motors(
            steering,
            brake_input
        )

        # ----------------------------------------------------
        # SAFETY OVERRIDE
        # ----------------------------------------------------

        if (
            emergency_lock
            and gear != REVERSE
        ):

            speed = 0

            left = 0
            right = 0

        # ----------------------------------------------------
        # SEND MOTOR COMMAND
        # ----------------------------------------------------

        if gear == REVERSE:

            send_motor(
                left,
                right,
                reverse=True
            )

        else:

            send_motor(
                left,
                right,
                reverse=False
            )

        # ----------------------------------------------------
        # HUD
        # ----------------------------------------------------

        draw_hud(
            steering,
            gas,
            brake_input,
            left,
            right
        )

        # ----------------------------------------------------
        # LOOP
        # ----------------------------------------------------

        clock.tick(LOOP_HZ)


except KeyboardInterrupt:

    print()
    print("Stopping...")


finally:

    stop()

    time.sleep(0.1)

    sock.close()

    pygame.quit()

    print("Car stopped.")