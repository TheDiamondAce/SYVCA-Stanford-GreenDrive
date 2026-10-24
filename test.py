import pygame
import time

pygame.init()
pygame.joystick.init()

wheel = pygame.joystick.Joystick(0)
wheel.init()

print("Controller:", wheel.get_name())
print("Axes:", wheel.get_numaxes())

while True:
    pygame.event.pump()

    steering = wheel.get_axis(0)

    print(f"\rSteering: {steering:+.4f}", end="")

    time.sleep(0.05)