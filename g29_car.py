import pygame
import socket
import json
import time
import select
import re
import os

# ============================================================
# GREEN DRIVE / DRIVE SENSE
# Logitech G29 -> Python -> Wi-Fi -> ELEGOO Smart Robot Car V4
# ============================================================


# ============================================================
# CONFIG
# ============================================================

CAR_IP = "192.168.4.1"
CAR_PORT = 100

LOOP_HZ = 20


# ============================================================
# MOTOR LIMITS
# ============================================================

ECO_MAX = 255
SPORT_MAX = 255

# Reverse is intentionally half-speed.
REVERSE_MAX = 127.5

ECO_ACCEL = 105.0
SPORT_ACCEL = 260.0

FRICTION = 45.0


# ============================================================
# BRAKING
# ============================================================
#
# The previous value of 260 was too soft.
#
# At 255 speed:
#
#   260 decel  -> ~0.98 sec
#   600 decel  -> ~0.43 sec
#   750 decel  -> ~0.34 sec
#
# We use a strong braking value so the robot responds
# much more like an actual brake pedal.
#

BRAKE_DECEL = 750.0
REVERSE_BRAKE_DECEL = 750.0

# Once the brake is pressed this far, aggressively reduce
# motor output instead of allowing the robot to continue
# driving through the brake.
BRAKE_MOTOR_CUTOFF = 0.18

# Above this brake level, force the motor command toward zero.
HARD_BRAKE_THRESHOLD = 0.65

# Once speed is extremely small, simply stop it.
BRAKE_STOP_THRESHOLD = 4.0


# ============================================================
# STEERING
# ============================================================

STEERING_GAIN = 0.85


# ============================================================
# PEDAL SETTINGS
# ============================================================

# Removes tiny accidental pedal values caused by G29 axis noise.
PEDAL_DEADZONE = 0.02


# ============================================================
# ULTRASONIC SAFETY
# ============================================================

SENSOR_INTERVAL = 0.25

EMERGENCY_DISTANCE = 20.0
RESET_DISTANCE = 50.0


# ============================================================
# SIMULATION
# ============================================================

ROBOT_LENGTH_M = 0.263
REAL_CAR_LENGTH_M = 4.50

MODEL_SCALE = (
    REAL_CAR_LENGTH_M
    / ROBOT_LENGTH_M
)

ROBOT_MAX_MPS = 0.75


# ============================================================
# SERVO / LOOK
# ============================================================

# Official ELEGOO V4 firmware:
#
# N = 106
#
# D1:
#   1 = Y down
#   2 = Y up
#   3 = Z right
#   4 = Z left
#   5 = center
#
# Corrected mapping:
#
#   Physical LEFT  -> 3
#   Physical RIGHT -> 4
#

SERVO_LOOK_LEFT = 3
SERVO_LOOK_RIGHT = 4
SERVO_LOOK_CENTER = 5

SERVO_REPEAT_INTERVAL = 0.08

SERVO_RANGE_STEPS = 8

servo_steps_left = 0
servo_steps_right = 0

last_servo_command_time = 0.0

last_look_direction = "CENTER"
previous_hat_x = 0


# ============================================================
# BLINKER SOUND
# ============================================================

SOUND_FOLDER = os.path.join(
    os.path.dirname(
        os.path.abspath(__file__)
    ),
    "sounds"
)

LEFT_BLINKER_SOUND = os.path.join(
    SOUND_FOLDER,
    "blinker_left.wav"
)

RIGHT_BLINKER_SOUND = os.path.join(
    SOUND_FOLDER,
    "blinker_right.wav"
)

STOP_BLINKER_SOUND = os.path.join(
    SOUND_FOLDER,
    "blinker_stop.wav"
)

BLINKER_SOUND_ENABLED = True


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


# ============================================================
# MOTOR COMMAND CACHE
# ============================================================

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
# G29 PADDLES
# ============================================================

PADDLE_LEFT_SIGNAL = 5
PADDLE_RIGHT_SIGNAL = 4


# ============================================================
# TURN SIGNAL STATE
# ============================================================

SIGNAL_OFF = "OFF"
SIGNAL_LEFT = "LEFT"
SIGNAL_RIGHT = "RIGHT"

AUTO_SIGNAL_CANCEL_THRESHOLD = 0.12

signal_turn_started = False

turn_signal = SIGNAL_OFF

signal_blink_state = False
last_signal_blink = 0.0

BLINK_INTERVAL = 0.45


# ============================================================
# LOOK STATE
# ============================================================

LOOK_CENTER = "CENTER"
LOOK_LEFT = "LEFT"
LOOK_RIGHT = "RIGHT"

look_direction = LOOK_CENTER


# ============================================================
# COLORS
# ============================================================

BG = (9, 12, 17)

PANEL = (18, 23, 31)
PANEL_LIGHT = (25, 31, 41)

BORDER = (43, 51, 63)

TEXT = (238, 242, 247)
MUTED = (135, 147, 161)

GREEN = (55, 225, 130)
GREEN_DARK = (35, 125, 80)

YELLOW = (245, 195, 65)
YELLOW_DARK = (130, 105, 35)

RED = (242, 75, 82)
RED_DARK = (125, 40, 45)

BLUE = (75, 165, 255)
BLUE_DARK = (45, 95, 150)

WHITE = (255, 255, 255)


# ============================================================
# PYGAME INITIALIZATION
# ============================================================

pygame.init()
pygame.font.init()
pygame.joystick.init()


# ============================================================
# OPTIONAL AUDIO
# ============================================================

sound_left = None
sound_right = None
sound_stop = None

try:

    pygame.mixer.init()

    if BLINKER_SOUND_ENABLED:

        if os.path.exists(
            LEFT_BLINKER_SOUND
        ):

            sound_left = pygame.mixer.Sound(
                LEFT_BLINKER_SOUND
            )

        if os.path.exists(
            RIGHT_BLINKER_SOUND
        ):

            sound_right = pygame.mixer.Sound(
                RIGHT_BLINKER_SOUND
            )

        if os.path.exists(
            STOP_BLINKER_SOUND
        ):

            sound_stop = pygame.mixer.Sound(
                STOP_BLINKER_SOUND
            )

except Exception as e:

    print(
        "Audio disabled:",
        e
    )


# ============================================================
# G29 DETECTION
# ============================================================

if pygame.joystick.get_count() == 0:

    print(
        "ERROR: G29 not detected."
    )

    pygame.quit()

    raise SystemExit


wheel = pygame.joystick.Joystick(0)
wheel.init()


print("=" * 60)
print("GREEN DRIVE")
print("=" * 60)
print(
    "Controller:",
    wheel.get_name()
)
print(
    "Axes:",
    wheel.get_numaxes()
)
print(
    "Buttons:",
    wheel.get_numbuttons()
)
print(
    "Hats:",
    wheel.get_numhats()
)
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
print("Left paddle  = LEFT SIGNAL")
print("Right paddle = RIGHT SIGNAL")
print()
print("D-PAD LEFT  = LOOK LEFT")
print("D-PAD RIGHT = LOOK RIGHT")
print()
print("Servo protocol: N=106")
print("=" * 60)


# ============================================================
# WIFI
# ============================================================

sock = socket.socket(
    socket.AF_INET,
    socket.SOCK_STREAM
)

sock.settimeout(3)

print(
    f"Connecting to {CAR_IP}:{CAR_PORT}..."
)

try:

    sock.connect(
        (CAR_IP, CAR_PORT)
    )

except Exception as e:

    print(
        "ERROR:",
        e
    )

    pygame.quit()

    raise SystemExit

print(
    "CONNECTED TO ELEGOO"
)

print()


# ============================================================
# MOTOR CONTROL
# ============================================================

def send_motor(
    left,
    right,
    reverse=False,
    force=False
):

    global last_left
    global last_right
    global last_reverse

    left = int(
        max(
            0,
            min(
                255,
                left
            )
        )
    )

    right = int(
        max(
            0,
            min(
                255,
                right
            )
        )
    )

    # Avoid unnecessary Wi-Fi traffic.
    if (
        not force
        and left == last_left
        and right == last_right
        and reverse == last_reverse
    ):

        return

    try:

        # ====================================================
        # REVERSE
        # ====================================================

        if reverse:

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
                json.dumps(
                    left_command
                ).encode()
            )

            sock.sendall(
                json.dumps(
                    right_command
                ).encode()
            )

        # ====================================================
        # FORWARD
        # ====================================================

        else:

            command = {
                "N": 4,
                "H": "G29",
                "D1": left,
                "D2": right
            }

            sock.sendall(
                json.dumps(
                    command
                ).encode()
            )

        last_left = left
        last_right = right
        last_reverse = reverse

    except Exception as e:

        print(
            "Motor error:",
            e
        )


# ============================================================
# STOP
# ============================================================

def stop():

    global speed
    global last_left
    global last_right
    global last_reverse

    speed = 0

    try:

        command = {
            "N": 1,
            "H": "STOP",
            "D1": 0,
            "D2": 0,
            "D3": 0
        }

        sock.sendall(
            json.dumps(
                command
            ).encode()
        )

    except Exception as e:

        print(
            "Stop error:",
            e
        )

    last_left = -1
    last_right = -1
    last_reverse = None


# ============================================================
# SERVO CONTROL
# ============================================================

def send_servo(command):

    global last_servo_command_time

    now = time.monotonic()

    if (
        now - last_servo_command_time
        < SERVO_REPEAT_INTERVAL
    ):

        return False

    last_servo_command_time = now

    try:

        packet = {
            "N": 106,
            "H": "LOOK",
            "D1": command
        }

        sock.sendall(
            json.dumps(
                packet
            ).encode()
        )

        return True

    except Exception as e:

        print(
            "Servo error:",
            e
        )

        return False


def update_look_servo(direction):

    global last_look_direction

    if direction == last_look_direction:

        return

    if direction == LOOK_LEFT:

        send_servo(
            SERVO_LOOK_LEFT
        )

    elif direction == LOOK_RIGHT:

        send_servo(
            SERVO_LOOK_RIGHT
        )

    else:

        send_servo(
            SERVO_LOOK_CENTER
        )

    last_look_direction = direction


# ============================================================
# ULTRASONIC
# ============================================================

def request_sensor():

    global last_sensor_time
    global sensor_id

    now = time.monotonic()

    if (
        now - last_sensor_time
        < SENSOR_INTERVAL
    ):

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
            json.dumps(
                command
            ).encode()
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

        data = sock.recv(
            4096
        )

        if not data:

            return

        text_data = data.decode(
            "utf-8",
            errors="ignore"
        )

        values = re.findall(
            r"US\d+_(-?\d+(?:\.\d+)?)",
            text_data
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

    # ========================================================
    # EMERGENCY BRAKE
    # ========================================================

    if (
        gear == DRIVE
        and ultrasonic_cm <= EMERGENCY_DISTANCE
        and not emergency_lock
    ):

        emergency_lock = True

        gear = NEUTRAL

        speed = 0

        stop()

        print()
        print(
            "!!! EMERGENCY BRAKE !!!"
        )
        print(
            f"Obstacle: {ultrasonic_cm:.1f} cm"
        )
        print(
            "DRIVE LOCKED"
        )
        print()

    # ========================================================
    # RESET
    # ========================================================

    if (
        emergency_lock
        and ultrasonic_cm >= RESET_DISTANCE
    ):

        emergency_lock = False

        print(
            "Safety distance restored."
        )

        print(
            "DRIVE UNLOCKED."
        )


# ============================================================
# INPUT
# ============================================================

previous_buttons = [
    False
] * wheel.get_numbuttons()


def button_pressed(
    button,
    current
):

    if button >= len(current):

        return False

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

    # ========================================================
    # GEAR BUTTONS
    # ========================================================

    if button_pressed(
        BUTTON_TRIANGLE,
        current
    ):

        # Do not allow DRIVE engagement while moving
        # backwards or while a safety lock is active.

        if not emergency_lock:

            if speed <= BRAKE_STOP_THRESHOLD:

                gear = DRIVE

            else:

                print(
                    "Cannot select DRIVE while moving."
                )

    elif button_pressed(
        BUTTON_SQUARE,
        current
    ):

        # Do not allow REVERSE while moving forward.

        if speed <= BRAKE_STOP_THRESHOLD:

            gear = REVERSE

        else:

            print(
                "Cannot select REVERSE while moving."
            )

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

        stop()

    # ========================================================
    # TURN SIGNALS
    # ========================================================

    if button_pressed(
        PADDLE_LEFT_SIGNAL,
        current
    ):

        if turn_signal == SIGNAL_LEFT:

            set_signal(
                SIGNAL_OFF
            )

        else:

            set_signal(
                SIGNAL_LEFT
            )

    if button_pressed(
        PADDLE_RIGHT_SIGNAL,
        current
    ):

        if turn_signal == SIGNAL_RIGHT:

            set_signal(
                SIGNAL_OFF
            )

        else:

            set_signal(
                SIGNAL_RIGHT
            )

    # ========================================================
    # SAVE BUTTONS
    # ========================================================

    for i in range(
        len(current)
    ):

        previous_buttons[i] = current[i]

    # ========================================================
    # KEYBOARD MODE
    # ========================================================

    keys = pygame.key.get_pressed()

    if keys[pygame.K_e]:

        mode = ECO

    elif keys[pygame.K_s]:

        mode = SPORT


# ============================================================
# TURN SIGNAL
# ============================================================

def set_signal(
    new_signal
):

    global turn_signal
    global signal_blink_state
    global last_signal_blink
    global signal_turn_started

    previous_signal = turn_signal

    turn_signal = new_signal

    # ========================================================
    # SIGNAL TURNED OFF
    # ========================================================

    if new_signal == SIGNAL_OFF:

        signal_turn_started = False
        signal_blink_state = False

        # Only play the stop sound if a signal was actually on.
        if (
            previous_signal != SIGNAL_OFF
            and BLINKER_SOUND_ENABLED
            and sound_stop is not None
        ):

            try:

                sound_stop.play()

            except Exception:

                pass

    # ========================================================
    # SIGNAL TURNED ON
    # ========================================================

    else:

        signal_blink_state = True

    last_signal_blink = time.monotonic()

    print(
        "TURN SIGNAL:",
        turn_signal
    )


def update_signal():

    global signal_blink_state
    global last_signal_blink

    if turn_signal == SIGNAL_OFF:

        signal_blink_state = False

        return

    now = time.monotonic()

    if (
        now - last_signal_blink
        >= BLINK_INTERVAL
    ):

        signal_blink_state = (
            not signal_blink_state
        )

        last_signal_blink = now

        # ====================================================
        # BLINKER SOUND
        # ====================================================

        if (
            signal_blink_state
            and BLINKER_SOUND_ENABLED
        ):

            try:

                if (
                    turn_signal == SIGNAL_LEFT
                    and sound_left is not None
                ):

                    sound_left.play()

                elif (
                    turn_signal == SIGNAL_RIGHT
                    and sound_right is not None
                ):

                    sound_right.play()

            except Exception:

                pass


def auto_cancel_signal(
    steering
):

    global turn_signal
    global signal_turn_started

    # No signal active.
    if turn_signal == SIGNAL_OFF:

        signal_turn_started = False

        return

    # Driver has actually started turning.
    if (
        abs(steering)
        > AUTO_SIGNAL_CANCEL_THRESHOLD
    ):

        signal_turn_started = True

        return

    # Driver has completed the turn and
    # straightened the wheel again.
    if signal_turn_started:

        set_signal(
            SIGNAL_OFF
        )

        signal_turn_started = False


# ============================================================
# D-PAD / SERVO
# ============================================================

def read_dpad():

    global look_direction
    global servo_steps_left
    global servo_steps_right
    global previous_hat_x

    if wheel.get_numhats() == 0:

        return

    hat_x, hat_y = wheel.get_hat(0)

    # ========================================================
    # LOOK LEFT
    # ========================================================

    if hat_x < 0:

        look_direction = LOOK_LEFT

        if servo_steps_left < SERVO_RANGE_STEPS:

            if send_servo(
                SERVO_LOOK_LEFT
            ):

                servo_steps_left += 1

        servo_steps_right = 0

    # ========================================================
    # LOOK RIGHT
    # ========================================================

    elif hat_x > 0:

        look_direction = LOOK_RIGHT

        if servo_steps_right < SERVO_RANGE_STEPS:

            if send_servo(
                SERVO_LOOK_RIGHT
            ):

                servo_steps_right += 1

        servo_steps_left = 0

    # ========================================================
    # D-PAD RELEASED
    # ========================================================

    else:

        look_direction = LOOK_CENTER

        servo_steps_left = 0
        servo_steps_right = 0

        # Only center when the D-pad was actually released
        # from a left/right position.

        if previous_hat_x != 0:

            send_servo(
                SERVO_LOOK_CENTER
            )

    previous_hat_x = hat_x


# ============================================================
# PEDALS
# ============================================================

def throttle():

    raw = wheel.get_axis(2)

    value = (
        1 - raw
    ) / 2

    value = max(
        0.0,
        min(
            1.0,
            value
        )
    )

    if value < PEDAL_DEADZONE:

        return 0.0

    return value


def brake():

    raw = wheel.get_axis(3)

    value = (
        1 - raw
    ) / 2

    value = max(
        0.0,
        min(
            1.0,
            value
        )
    )

    if value < PEDAL_DEADZONE:

        return 0.0

    return value


# ============================================================
# VEHICLE PHYSICS
# ============================================================

def update_physics(
    dt,
    gas,
    brake_input
):

    global speed

    # ========================================================
    # BRAKING
    # ========================================================
    #
    # Brake takes priority over throttle.
    #
    # The important change is that braking is now much stronger
    # and reaches zero quickly.
    #

    if brake_input > 0.01:

        if gear == REVERSE:

            deceleration = (
                REVERSE_BRAKE_DECEL
                * brake_input
            )

        else:

            deceleration = (
                BRAKE_DECEL
                * brake_input
            )

        speed -= (
            deceleration * dt
        )

        # Prevent tiny residual speed from hanging around.
        if (
            speed <= BRAKE_STOP_THRESHOLD
            or brake_input >= HARD_BRAKE_THRESHOLD
        ):

            speed = 0.0

        else:

            speed = max(
                0.0,
                speed
            )

        return

    # ========================================================
    # MODE
    # ========================================================

    if mode == ECO:

        max_speed = ECO_MAX

        acceleration = ECO_ACCEL

    else:

        max_speed = SPORT_MAX

        acceleration = SPORT_ACCEL

    # ========================================================
    # TARGET
    # ========================================================

    if gear == REVERSE:

        target = (
            gas * REVERSE_MAX
        )

    elif gear == DRIVE:

        target = (
            gas * max_speed
        )

    else:

        target = 0.0

    # ========================================================
    # ACCELERATE
    # ========================================================

    if speed < target:

        speed += (
            acceleration * dt
        )

        speed = min(
            speed,
            target
        )

    # ========================================================
    # THROTTLE RELEASE
    # ========================================================

    elif gas <= 0.01:

        speed -= (
            FRICTION * dt
        )

        speed = max(
            0.0,
            speed
        )

    # ========================================================
    # RETURN TOWARD TARGET
    # ========================================================

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

    if emergency_lock:

        return 0, 0

    # ========================================================
    # STEERING
    # ========================================================

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

    # ========================================================
    # BRAKE MOTOR EFFECT
    # ========================================================

    if brake_input > 0.01:

        # At 0% brake:
        #     100% motor output
        #
        # At 50% brake:
        #     50% motor output
        #
        # At 100% brake:
        #     0% motor output

        brake_factor = (
            1.0 - brake_input
        )

        left *= brake_factor
        right *= brake_factor

        # ====================================================
        # HARD BRAKE CUTOFF
        # ====================================================
        #
        # This prevents a deep brake pedal from continuing
        # to send meaningful motor power to the robot.
        #

        if brake_input >= BRAKE_MOTOR_CUTOFF:

            cutoff_ratio = (
                1.0
                - (
                    brake_input
                    - BRAKE_MOTOR_CUTOFF
                )
                / (
                    1.0
                    - BRAKE_MOTOR_CUTOFF
                )
            )

            cutoff_ratio = max(
                0.0,
                min(
                    1.0,
                    cutoff_ratio
                )
            )

            left *= cutoff_ratio
            right *= cutoff_ratio

    # ========================================================
    # STOPPED
    # ========================================================

    if (
        brake_input >= HARD_BRAKE_THRESHOLD
        or speed <= BRAKE_STOP_THRESHOLD
    ):

        left = 0
        right = 0

    # ========================================================
    # LIMIT
    # ========================================================

    left = max(
        0.0,
        min(
            255.0,
            left
        )
    )

    right = max(
        0.0,
        min(
            255.0,
            right
        )
    )

    return left, right


# ============================================================
# SIMULATED SPEED
# ============================================================

def simulated_speed():

    ratio = (
        speed
        / 255.0
    )

    ratio = max(
        0.0,
        min(
            1.0,
            ratio
        )
    )

    robot_mps = (
        ratio
        * ROBOT_MAX_MPS
    )

    full_size_mps = (
        robot_mps
        * MODEL_SCALE
    )

    kmh = (
        full_size_mps
        * 3.6
    )

    mph = (
        full_size_mps
        * 2.236936
    )

    return kmh, mph


# ============================================================
# HUD SETUP
# ============================================================

screen = pygame.display.set_mode(
    (1200, 760)
)

pygame.display.set_caption(
    "GreenDrive — DriveSense"
)

clock = pygame.time.Clock()


font_title = pygame.font.Font(
    None,
    48
)

font_speed = pygame.font.Font(
    None,
    88
)

font_gear = pygame.font.Font(
    None,
    72
)

font_large = pygame.font.Font(
    None,
    36
)

font_medium = pygame.font.Font(
    None,
    28
)

font_small = pygame.font.Font(
    None,
    22
)

font_tiny = pygame.font.Font(
    None,
    18
)


# ============================================================
# HUD HELPERS
# ============================================================

def draw_text(
    value,
    x,
    y,
    font,
    color=TEXT
):

    surface = font.render(
        str(value),
        True,
        color
    )

    screen.blit(
        surface,
        (x, y)
    )


def panel(
    x,
    y,
    w,
    h
):

    pygame.draw.rect(
        screen,
        PANEL,
        (x, y, w, h),
        border_radius=16
    )

    pygame.draw.rect(
        screen,
        BORDER,
        (x, y, w, h),
        width=1,
        border_radius=16
    )


def bar(
    x,
    y,
    w,
    h,
    value,
    color
):

    value = max(
        0.0,
        min(
            1.0,
            value
        )
    )

    pygame.draw.rect(
        screen,
        PANEL_LIGHT,
        (x, y, w, h),
        border_radius=6
    )

    fill = int(
        w * value
    )

    if fill > 0:

        pygame.draw.rect(
            screen,
            color,
            (x, y, fill, h),
            border_radius=6
        )


def centered_text(
    value,
    center_x,
    y,
    font,
    color=TEXT
):

    surface = font.render(
        str(value),
        True,
        color
    )

    rect = surface.get_rect()

    rect.centerx = center_x

    rect.y = y

    screen.blit(
        surface,
        rect
    )


# ============================================================
# SIGNAL ICON
# ============================================================

def draw_signal_indicator(
    x,
    y,
    direction,
    active
):

    color = (
        YELLOW
        if active
        else MUTED
    )

    if direction == "LEFT":

        points = [
            (x, y + 15),
            (x + 24, y),
            (x + 24, y + 10),
            (x + 55, y + 10),
            (x + 55, y + 20),
            (x + 24, y + 20),
            (x + 24, y + 30)
        ]

    else:

        points = [
            (x + 55, y + 15),
            (x + 31, y),
            (x + 31, y + 10),
            (x, y + 10),
            (x, y + 20),
            (x + 31, y + 20),
            (x + 31, y + 30)
        ]

    pygame.draw.polygon(
        screen,
        color,
        points
    )


# ============================================================
# HUD
# ============================================================

def draw_hud(
    steering,
    gas,
    brake_input,
    left,
    right
):

    screen.fill(BG)

    kmh, mph = simulated_speed()

    # Keep HUD steering normal while control remains inverted.
    hud_steering = -steering

    # ========================================================
    # HEADER
    # ========================================================

    draw_text(
        "GREEN DRIVE",
        35,
        24,
        font_title
    )

    draw_text(
        "G29  •  DRIVE SENSE  •  ELEGOO V4.0",
        38,
        72,
        font_small,
        MUTED
    )

    pygame.draw.circle(
        screen,
        GREEN,
        (1080, 44),
        7
    )

    draw_text(
        "CONNECTED",
        1100,
        32,
        font_small,
        GREEN
    )

    # ========================================================
    # TURN SIGNAL BAR
    # ========================================================

    panel(
        35,
        105,
        1130,
        65
    )

    left_active = (
        turn_signal == SIGNAL_LEFT
        and signal_blink_state
    )

    right_active = (
        turn_signal == SIGNAL_RIGHT
        and signal_blink_state
    )

    draw_signal_indicator(
        70,
        122,
        "LEFT",
        left_active
    )

    draw_signal_indicator(
        1050,
        122,
        "RIGHT",
        right_active
    )

    if turn_signal == SIGNAL_LEFT:

        centered_text(
            "LEFT TURN SIGNAL",
            600,
            123,
            font_medium,
            YELLOW
        )

    elif turn_signal == SIGNAL_RIGHT:

        centered_text(
            "RIGHT TURN SIGNAL",
            600,
            123,
            font_medium,
            YELLOW
        )

    else:

        centered_text(
            "SIGNALS OFF",
            600,
            123,
            font_medium,
            MUTED
        )

    # ========================================================
    # SPEED PANEL
    # ========================================================

    panel(
        35,
        190,
        470,
        270
    )

    draw_text(
        "VEHICLE SPEED",
        65,
        215,
        font_small,
        MUTED
    )

    draw_text(
        f"{kmh:05.1f}",
        65,
        245,
        font_speed
    )

    draw_text(
        "km/h",
        70,
        350,
        font_medium,
        MUTED
    )

    draw_text(
        f"{mph:04.1f} mph",
        190,
        354,
        font_small,
        MUTED
    )

    bar(
        65,
        405,
        390,
        14,
        speed / 255.0,
        BLUE
    )

    draw_text(
        "MAX MOTOR OUTPUT  255",
        65,
        425,
        font_tiny,
        MUTED
    )

    # ========================================================
    # GEAR PANEL
    # ========================================================

    panel(
        530,
        190,
        220,
        270
    )

    draw_text(
        "GEAR",
        560,
        215,
        font_small,
        MUTED
    )

    gear_colors = {
        PARK: RED,
        REVERSE: YELLOW,
        NEUTRAL: MUTED,
        DRIVE: GREEN
    }

    gear_names = {
        PARK: "PARK",
        REVERSE: "REVERSE",
        NEUTRAL: "NEUTRAL",
        DRIVE: "DRIVE"
    }

    draw_text(
        gear,
        605,
        250,
        font_gear,
        gear_colors[gear]
    )

    centered_text(
        gear_names[gear],
        640,
        350,
        font_small,
        gear_colors[gear]
    )

    # ========================================================
    # MODE PANEL
    # ========================================================

    panel(
        775,
        190,
        390,
        270
    )

    draw_text(
        "DRIVE MODE",
        805,
        215,
        font_small,
        MUTED
    )

    mode_color = (
        GREEN
        if mode == ECO
        else YELLOW
    )

    centered_text(
        mode,
        970,
        260,
        font_large,
        mode_color
    )

    if mode == ECO:

        draw_text(
            "Efficient acceleration",
            830,
            325,
            font_small,
            MUTED
        )

        draw_text(
            "E",
            820,
            370,
            font_large,
            GREEN
        )

    else:

        draw_text(
            "Sport acceleration",
            840,
            325,
            font_small,
            MUTED
        )

        draw_text(
            "S",
            820,
            370,
            font_large,
            YELLOW
        )

    # ========================================================
    # INPUT PANEL
    # ========================================================

    panel(
        35,
        485,
        470,
        235
    )

    draw_text(
        "DRIVER INPUT",
        65,
        510,
        font_small,
        MUTED
    )

    draw_text(
        f"STEERING   {hud_steering:+.2f}",
        65,
        550,
        font_medium
    )

    pygame.draw.rect(
        screen,
        PANEL_LIGHT,
        (65, 595, 390, 12),
        border_radius=6
    )

    steering_x = (
        65
        + int(
            ((hud_steering + 1) / 2)
            * 390
        )
    )

    pygame.draw.circle(
        screen,
        BLUE,
        (steering_x, 601),
        8
    )

    draw_text(
        f"THROTTLE   {gas * 100:3.0f}%",
        65,
        635,
        font_small
    )

    bar(
        250,
        640,
        205,
        12,
        gas,
        GREEN
    )

    draw_text(
        f"BRAKE      {brake_input * 100:3.0f}%",
        65,
        675,
        font_small
    )

    bar(
        250,
        680,
        205,
        12,
        brake_input,
        RED
    )

    # ========================================================
    # MOTOR PANEL
    # ========================================================

    panel(
        530,
        485,
        380,
        235
    )

    draw_text(
        "MOTOR OUTPUT",
        560,
        510,
        font_small,
        MUTED
    )

    draw_text(
        f"LEFT     {left:3.0f}",
        560,
        555,
        font_medium
    )

    bar(
        560,
        600,
        310,
        14,
        left / 255,
        BLUE
    )

    draw_text(
        f"RIGHT    {right:3.0f}",
        560,
        635,
        font_medium
    )

    bar(
        560,
        680,
        310,
        14,
        right / 255,
        BLUE
    )

    # ========================================================
    # TELEMETRY / SAFETY
    # ========================================================

    panel(
        935,
        485,
        230,
        235
    )

    draw_text(
        "TELEMETRY",
        960,
        510,
        font_small,
        MUTED
    )

    draw_text(
        "ULTRASONIC",
        960,
        550,
        font_tiny,
        MUTED
    )

    if ultrasonic_cm is None:

        distance_text = "--"
        distance_color = MUTED

    else:

        distance_text = (
            f"{ultrasonic_cm:.0f} cm"
        )

        if ultrasonic_cm <= 20:

            distance_color = RED

        elif ultrasonic_cm <= 50:

            distance_color = YELLOW

        else:

            distance_color = GREEN

    centered_text(
        distance_text,
        1050,
        570,
        font_medium,
        distance_color
    )

    if emergency_lock:

        centered_text(
            "EMERGENCY",
            1050,
            625,
            font_small,
            RED
        )

        centered_text(
            "DRIVE LOCKED",
            1050,
            650,
            font_tiny,
            RED
        )

    else:

        centered_text(
            "SYSTEM CLEAR",
            1050,
            625,
            font_small,
            GREEN
        )

    # ========================================================
    # LOOK
    # ========================================================

    if look_direction == LOOK_LEFT:

        look_text = "<  LOOK LEFT"

    elif look_direction == LOOK_RIGHT:

        look_text = "LOOK RIGHT  >"

    else:

        look_text = "LOOK CENTER"

    centered_text(
        look_text,
        1050,
        680,
        font_tiny,
        BLUE
    )

    # ========================================================
    # FOOTER
    # ========================================================

    draw_text(
        "△ DRIVE   □ REVERSE   ○ NEUTRAL   ✕ PARK",
        35,
        735,
        font_tiny,
        MUTED
    )

    draw_text(
        "PADDLES: SIGNALS",
        450,
        735,
        font_tiny,
        MUTED
    )

    draw_text(
        "D-PAD: LOOK",
        690,
        735,
        font_tiny,
        MUTED
    )

    draw_text(
        "E ECO  •  S SPORT",
        890,
        735,
        font_tiny,
        MUTED
    )

    pygame.display.flip()


# ============================================================
# MAIN LOOP
# ============================================================

last_time = time.monotonic()

try:

    while True:

        # ====================================================
        # EVENTS
        # ====================================================

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

        # ====================================================
        # TIME
        # ====================================================

        now = time.monotonic()

        dt = (
            now
            - last_time
        )

        last_time = now

        dt = min(
            dt,
            0.1
        )

        # ====================================================
        # INPUT
        # ====================================================

        read_inputs()

        # ====================================================
        # STEERING
        # ====================================================

        steering = -wheel.get_axis(0)

        steering = max(
            -1.0,
            min(
                1.0,
                steering
            )
        )

        auto_cancel_signal(
            steering
        )

        # ====================================================
        # PEDALS
        # ====================================================

        gas = throttle()

        brake_input = brake()

        # ====================================================
        # D-PAD / SERVO
        # ====================================================

        read_dpad()

        # ====================================================
        # SIGNAL BLINKING
        # ====================================================

        update_signal()

        # ====================================================
        # SENSOR
        # ====================================================

        request_sensor()

        read_sensor()

        # ====================================================
        # SAFETY
        # ====================================================

        safety_check()

        # ====================================================
        # PHYSICS
        # ====================================================

        update_physics(
            dt,
            gas,
            brake_input
        )

        # ====================================================
        # MOTOR OUTPUT
        # ====================================================

        left, right = calculate_motors(
            steering,
            brake_input
        )

        # ====================================================
        # EMERGENCY OVERRIDE
        # ====================================================

        if emergency_lock:

            if gear not in (
                REVERSE,
                NEUTRAL,
                PARK
            ):

                gear = NEUTRAL

            if gear != REVERSE:

                speed = 0

                left = 0
                right = 0

        # ====================================================
        # SEND TO ROBOT
        # ====================================================

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

        # ====================================================
        # HUD
        # ====================================================

        draw_hud(
            steering,
            gas,
            brake_input,
            left,
            right
        )

        # ====================================================
        # LOOP RATE
        # ====================================================

        clock.tick(
            LOOP_HZ
        )


except KeyboardInterrupt:

    print()
    print(
        "Stopping GreenDrive..."
    )


finally:

    stop()

    time.sleep(
        0.1
    )

    try:

        sock.close()

    except Exception:

        pass

    pygame.quit()

    print(
        "GreenDrive stopped."
    )