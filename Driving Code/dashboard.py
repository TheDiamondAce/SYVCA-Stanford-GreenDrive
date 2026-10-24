import tkinter as tk
import serial
import random
import time
import threading

# --- 1. SETUP YOUR BLUETOOTH PORT ---
# Look in your Mac settings or Arduino IDE port list for the HC-05/HC-06 port.
BAUD_RATE = 9600

try:
    bt = serial.Serial(BLUETOOTH_PORT, BAUD_RATE, timeout=1)
    print("Bluetooth Connected! Click the black window and use WASD to drive.")
except Exception as e:
    print(f"Warning: Bluetooth not connected. Running UI only. Error: {e}")
    bt = None

# --- STATE VARIABLES ---
aqi = 50
speed_limit = 100
current_key = None

# --- 2. THE DATA SIMULATOR ---
def update_emissions():
    global aqi, speed_limit
    while True:
        # Randomly fluctuate the AQI
        aqi += random.randint(-15, 20)
        if aqi < 0: aqi = 0
        if aqi > 150: aqi = 150
        
        # The Logic: High AQI = Lower Speed Limit
        if aqi < 50:
            speed_limit = 100
            color = "#00FF00" # Green
        elif aqi < 100:
            speed_limit = 60
            color = "#FFA500" # Orange
        else:
            speed_limit = 30
            color = "#FF0000" # Red
            
        # Update the visual HUD
        aqi_label.config(text=f"EMISSIONS AQI: {aqi}", fg=color)
        speed_label.config(text=f"MAX SPEED: {speed_limit}%", fg=color)
        time.sleep(2.5)

# --- 3. THE BLUETOOTH MOTOR PULSER ---
def motor_loop():
    global current_key
    while True:
        if current_key and bt:
            # Send the WASD command
            bt.write(current_key.encode())
            
            # If emissions are high, we "stutter" the motor to slow it down
            if speed_limit == 100:
                time.sleep(0.1) # Full power
            elif speed_limit == 60:
                time.sleep(0.06)
                bt.write(b'X') # Cut power briefly
                time.sleep(0.04)
            else:
                time.sleep(0.03)
                bt.write(b'X') # Cut power drastically
                time.sleep(0.07)
        else:
            if bt: bt.write(b'X') # Stop if no key pressed
            time.sleep(0.1)

# --- 4. KEYBOARD CONTROLS ---
def key_down(event):
    global current_key
    char = event.char.upper()
    if char in ['W', 'A', 'S', 'D']:
        current_key = char

def key_up(event):
    global current_key
    char = event.char.upper()
    if char == current_key:
        current_key = None
        if bt: bt.write(b'X')

# --- 5. BUILD THE VISUAL HUD WINDOW ---
root = tk.Tk()
root.title("Stanford Climate Hackathon - Smart Governor")
root.geometry("600x300")
root.configure(bg="black") # Black background makes it easy to Chroma Key in OBS

aqi_label = tk.Label(root, text="EMISSIONS AQI: 50", font=("Helvetica", 48, "bold"), bg="black", fg="#00FF00")
aqi_label.pack(pady=40)

speed_label = tk.Label(root, text="MAX SPEED: 100%", font=("Helvetica", 36, "bold"), bg="black", fg="#00FF00")
speed_label.pack()

# Bind keys to the window (YOU MUST CLICK THE WINDOW FOR WASD TO WORK)
root.bind("<KeyPress>", key_down)
root.bind("<KeyRelease>", key_up)

# Start background threads
threading.Thread(target=update_emissions, daemon=True).start()
threading.Thread(target=motor_loop, daemon=True).start()

root.mainloop()