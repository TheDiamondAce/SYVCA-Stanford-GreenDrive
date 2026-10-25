
import pygame
import time

# ============================================================
# GREEN DRIVE / DRIVE SENSE — HUD DEMO
# ============================================================
# Standalone screenshot/demo version of the real GreenDrive HUD.
# No G29, Wi-Fi, ESP32, UNO, servo, or robot connection is used.
#
# The HUD itself is taken directly from the real GreenDrive code.
# Only the hardware/network/main-loop layer has been replaced.
# ============================================================

LOOP_HZ = 60

# ============================================================
# STATES
# ============================================================

PARK = "P"
REVERSE = "R"
NEUTRAL = "N"
DRIVE = "D"

ECO = "ECO"
SPORT = "SPORT"

SIGNAL_OFF = "OFF"
SIGNAL_LEFT = "LEFT"
SIGNAL_RIGHT = "RIGHT"

LOOK_CENTER = "CENTER"
LOOK_LEFT = "LEFT"
LOOK_RIGHT = "RIGHT"

gear = DRIVE
mode = ECO

# Fake starting values
speed = 233.5
ultrasonic_cm = 86.0
emergency_lock = False

turn_signal = SIGNAL_LEFT
signal_blink_state = True

look_direction = LOOK_LEFT

# Demo driver inputs
steering = -0.22
_gas = 0.64
_brake = 0.00

left = 183
right = 211

# ============================================================
# SAME SPEED SCALING AS REAL GREENDRIVE
# ============================================================

ROBOT_LENGTH_M = 0.263
REAL_CAR_LENGTH_M = 4.50

MODEL_SCALE = (
    REAL_CAR_LENGTH_M
    / ROBOT_LENGTH_M
)

ROBOT_MAX_MPS = 0.75

# ============================================================
# COLORS — SAME AS REAL HUD
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

pygame.init()
pygame.font.init()

# ============================================================
# HUD SETUP
# ============================================================

screen = pygame.display.set_mode(
    (1200, 760)
)

pygame.display.set_caption(
    "GreenDrive — DriveSense — HUD Demo"
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


def draw_hud():
    screen.fill(BG)

    draw_text("GREEN DRIVE", 35, 24, font_title)
    draw_text(
        "DRIVE SENSE  •  HUD DEMO",
        38,
        72,
        font_small,
        MUTED
    )

    pygame.draw.circle(screen, GREEN, (1080, 44), 7)
    draw_text("SIMULATION", 1095, 32, font_small, GREEN)

    panel(35, 105, 1130, 65)
    left_active = turn_signal == SIGNAL_LEFT and signal_blink_state
    right_active = turn_signal == SIGNAL_RIGHT and signal_blink_state
    draw_signal_indicator(70, 122, "LEFT", left_active)
    draw_signal_indicator(1050, 122, "RIGHT", right_active)

    if turn_signal == SIGNAL_LEFT:
        centered_text("LEFT TURN SIGNAL", 600, 123, font_medium, YELLOW)
    elif turn_signal == SIGNAL_RIGHT:
        centered_text("RIGHT TURN SIGNAL", 600, 123, font_medium, YELLOW)
    else:
        centered_text("SIGNALS OFF", 600, 123, font_medium, MUTED)

    panel(35, 195, 530, 300)
    draw_text("SPEED", 65, 225, font_medium, MUTED)
    centered_text(f"{speed:05.1f}", 300, 265, font_speed)
    draw_text("km/h", 425, 315, font_medium, MUTED)
    draw_text("DRIVE MODE", 65, 405, font_small, MUTED)
    draw_text(mode, 65, 430, font_large, GREEN if mode == ECO else YELLOW)

    panel(595, 195, 570, 300)
    draw_text("GEAR", 625, 225, font_medium, MUTED)
    centered_text(gear, 880, 265, font_gear, GREEN)
    draw_text("DISTANCE", 625, 405, font_small, MUTED)
    distance_color = RED if ultrasonic_cm < 30 else GREEN
    draw_text(f"{ultrasonic_cm:.0f} cm", 625, 430, font_large, distance_color)

    panel(35, 525, 1130, 145)
    draw_text("STEERING", 65, 555, font_small, MUTED)
    bar(65, 595, 310, 24, (steering + 1.0) / 2.0, BLUE)
    draw_text(f"{steering:+.2f}", 390, 590, font_small)
    draw_text("THROTTLE", 535, 555, font_small, MUTED)
    bar(535, 595, 240, 24, _gas, GREEN)
    draw_text(f"{_gas:.0%}", 790, 590, font_small)
    draw_text("BRAKE", 900, 555, font_small, MUTED)
    bar(900, 595, 180, 24, _brake, RED)
    draw_text(f"{_brake:.0%}", 1090, 590, font_small)

    draw_text(
        "A: left  •  D: right  •  SPACE: off  •  G: gear  •  M: mode  •  ESC: quit",
        35,
        710,
        font_tiny,
        MUTED
    )


def update_demo(dt):
    global speed, signal_blink_state

    target_speed = _gas * 255.0
    if _brake > 0:
        target_speed = 0.0

    speed += (target_speed - speed) * min(1.0, dt * 4.0)

    if turn_signal != SIGNAL_OFF:
        signal_blink_state = (
            int(time.monotonic() / 0.45) % 2 == 0
        )


def run():
    global gear, mode, turn_signal, steering, _gas, _brake

    running = True
    last_time = time.monotonic()

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_g:
                    gear = {
                        PARK: REVERSE,
                        REVERSE: NEUTRAL,
                        NEUTRAL: DRIVE,
                        DRIVE: PARK
                    }[gear]
                elif event.key == pygame.K_m:
                    mode = SPORT if mode == ECO else ECO
                elif event.key == pygame.K_a:
                    turn_signal = (
                        SIGNAL_OFF
                        if turn_signal == SIGNAL_LEFT
                        else SIGNAL_LEFT
                    )
                    signal_blink_state = True
                elif event.key == pygame.K_d:
                    turn_signal = (
                        SIGNAL_OFF
                        if turn_signal == SIGNAL_RIGHT
                        else SIGNAL_RIGHT
                    )
                    signal_blink_state = True
                elif event.key == pygame.K_SPACE:
                    turn_signal = (
                        SIGNAL_OFF
                        if turn_signal != SIGNAL_OFF
                        else SIGNAL_LEFT
                    )
            elif event.type == pygame.KEYUP and event.key == pygame.K_SPACE:
                signal_blink_state = False

        keys = pygame.key.get_pressed()
        steering = float(keys[pygame.K_RIGHT]) - float(keys[pygame.K_LEFT])
        _gas = float(keys[pygame.K_UP])
        _brake = float(keys[pygame.K_DOWN])

        now = time.monotonic()
        dt = min(now - last_time, 0.1)
        last_time = now
        update_demo(dt)
        draw_hud()
        pygame.display.flip()
        clock.tick(LOOP_HZ)


if __name__ == "__main__":
    try:
        run()
    finally:
        pygame.quit()