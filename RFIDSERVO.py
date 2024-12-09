import RPi.GPIO as GPIO
from mfrc522 import SimpleMFRC522
import time
import json
import os
import requests
from urllib.parse import urlencode

# Initialize GPIO and RFID reader
GPIO.cleanup()  # Clean up any previous settings
GPIO.setwarnings(False)
GPIO.setmode(GPIO.BCM)
reader = SimpleMFRC522()

# File to store card states
state_file = 'card_states.json'
# Your web server URL
webserver_url = 'http://yourwebserver.com/endpoint'

# GPIO setup for servo, button, and buzzer
SERVO_PIN = 16
BUTTON_PIN = 19
BUZZER_PIN = 21

GPIO.setup(SERVO_PIN, GPIO.OUT)
GPIO.setup(BUTTON_PIN, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(BUZZER_PIN, GPIO.OUT)

# Initialize servo
servo = GPIO.PWM(SERVO_PIN, 50)  # 50 Hz
servo.start(0)

# Buzzer functions
def buzzer_on(duration=1):
    GPIO.output(BUZZER_PIN, GPIO.HIGH)
    time.sleep(duration)
    GPIO.output(BUZZER_PIN, GPIO.LOW)

def buzzer_single_beep():
    buzzer_on(0.2)

def buzzer_double_beep():
    buzzer_on(0.2)
    time.sleep(0.2)
    buzzer_on(0.2)

# Function to open the servo (turn to 90 degrees)
def open_servo(duration=3):
    servo.ChangeDutyCycle(7)  # Adjust the duty cycle to 7 for 90 degrees
    print(f"Servo opened for {duration} seconds")
    time.sleep(duration)  # Wait for the specified duration
    servo.ChangeDutyCycle(0)  # Turn off the servo

# Function to close the servo (turn to 0 degrees)
def close_servo():
    servo.ChangeDutyCycle(2)  # Adjust the duty cycle to 2 for 0 degrees
    print("Servo closed (0 degrees)")
    time.sleep(0.5)
    servo.ChangeDutyCycle(0)  # Turn off the servo

# Startup sequence: Open servo for 1 second and buzz
open_servo(1)
close_servo()
buzzer_on(1)

# Load card states from file
def load_card_states():
    if os.path.exists(state_file):
        with open(state_file, 'r') as file:
            try:
                return json.load(file)
            except json.JSONDecodeError:
                print("Error decoding JSON file, starting with an empty dictionary.")
                return {}
    return {}

# Save card states to file
def save_card_states(states):
    with open(state_file, 'w') as file:
        json.dump(states, file, indent=4)
    print(f"Card states saved to file: {states}")

# Send HTTP POST request to the webserver
def post_to_webserver(card_id, status):
    try:
        payload = {'card_id': card_id, 'status': status}
        url_with_params = f"{webserver_url}?{urlencode(payload)}"
        print(f"Full URL: {url_with_params}")
        response = requests.post(webserver_url, json=payload)
        print(f"Posted to webserver: {response.status_code}, {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"Error posting to webserver: {e}")

# Dictionary to keep track of card states
card_states = load_card_states()
print(f"Loaded card states: {card_states}")

def read_card():
    try:
        id, text = reader.read_no_block()
        if id:
            return str(id)  # Ensure ID is treated as a string for consistency
        return None
    except Exception as e:
        print(f"Error while reading card: {e}")
        return None

print("Place your card near the reader...")

try:
    while True:
        card_id = read_card()
        if card_id:
            # Reload the card states from the file to ensure we have the latest version
            card_states = load_card_states()
            
            current_state = card_states.get(card_id, "OUT")
            if current_state == "OUT":
                card_states[card_id] = "IN"
                print(f"Card ID {card_id} checked IN")
                post_to_webserver(card_id, "IN")
                buzzer_single_beep()
            elif current_state == "IN":
                card_states[card_id] = "OUT"
                print(f"Card ID {card_id} checked OUT")
                post_to_webserver(card_id, "OUT")
                buzzer_double_beep()
            
            # Save the updated states to the file
            save_card_states(card_states)
            
            # Wait for button press to open the servo
            print("Waiting for button press to open the servo...")
            while GPIO.input(BUTTON_PIN) == GPIO.HIGH:
                time.sleep(0.01)  # Polling delay to avoid high CPU usage
            open_servo()
            close_servo()
            
            # Add a small delay to avoid reading the card multiple times immediately
            time.sleep(1)
        time.sleep(0.1)
finally:
    GPIO.cleanup()
    servo.stop()
    # Ensure states are saved on exit
    save_card_states(card_states)
