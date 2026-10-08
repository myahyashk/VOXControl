import google
import vosk
import pyaudio
import webbrowser
import json
import pyttsx3
import os
import requests
from tkinter import Tk, Button, Label, Text, END
import threading
import numpy as np
import matplotlib.backends.backend_tkagg as tkagg
import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
import tkinter as tk
import google.generativeai as genai

from retrying import retry

# Resolve the model relative to this project, so it works on Linux and Windows.
model_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'models', 'vosk-model-en-in-0.5'))


# Initialize speech synthesis engine
engine = pyttsx3.init()
engine.setProperty('rate', 150)
engine.setProperty('volume', 1.0)


def speak(text):
    engine.say(text)
    engine.runAndWait()


# Initialize Vosk with the specified model path
vosk.SetLogLevel(-1)
model = vosk.Model(model_path)
recognizer = vosk.KaldiRecognizer(model, 16000)

# Flag to track if the listening session is active
listening_active = False
speak("Hello Boss JOYO Here")
print("Hello Boss JOYO Here")
speak("How may i help You Today")
print("How may i help You Today")


# Gemini Code Start
# Function to check internet connectivity
def is_connected():
    try:
        requests.get("http://google.com", timeout=3)
        return True
    except requests.ConnectionError:
        return False


# Retry decorator to retry sending message if not connected
@retry(stop_max_attempt_number=3, wait_fixed=2000)
def send_message(user_input):
    if user_input:
        convo.send_message(user_input)
        response = convo.last.text
        print(f"You: {user_input}")
        print(f"JOYOPoweredGemini: {response}\n")
        speak(response)


def clear_input():
    pass  # Since there's no GUI, clearing input is not necessary


# Load the Gemini credential from the environment instead of source control.
gemini_api_key = os.environ.get("GEMINI_API_KEY")
if gemini_api_key:
    genai.configure(api_key=gemini_api_key)

# Set up the model(not initialized by ahsan)
generation_config = {
    "temperature": 0.7,
    "top_p": 1,
    "top_k": 1,
    "max_output_tokens": 2048,
}

model_gemini = genai.GenerativeModel(model_name="gemini-2.0-flash")

convo = model_gemini.start_chat(history=[])


# gemini Code end
# shutdownHibernateSleepRestartFunction Starts Here
def shutdown():
    os.system("shutdown /s /t 1")  # Shutdown after 1 second


def hibernate():
    os.system("shutdown /h /f")


def restart():
    os.system("shutdown /r /t 1")  # Restart after 1 second


def sleep():
    os.system("rundll32.exe powrprof.dll,SetSuspendState 0,1,0")  # Put to sleep


def open_gym():
    speak("Opening website")
    webbrowser.open("https://gym-website-muhammad-shafiullah.netlify.app")  # Change the URL as needed


# shutdownHibernateSleepRestartFunction Ends Here




# calculate age site
def agecheck():
    speak("opening checkyourage.com")
    webbrowser.open("https://checkyourage.netlify.app/")  # Change the URL as needed
    print("Opening AgeCalculator...")


# calculate age end

def portfolio():
    speak("open Raza Portfolio")
    webbrowser.open("https://ahsanrazabaloch.netlify.app/")  # Change the URL as needed
    print("Opening Portfolio...")


# check your ip function
def get_current_ip_details():
    url = "http://ip-api.com/json/"
    response = requests.get(url)
    data = response.json()
    return data


# functions for usage ends


# Function to listen and recognize speech
def listen_and_recognize(recognized_text):
    global listening_active
    if listening_active:
        print("Listening session is already active.")
        return
    listening_active = True
    audio = pyaudio.PyAudio()
    stream = audio.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True, frames_per_buffer=8000)
    print("Listening...")
    while True:
        try:
            data = stream.read(8000)
            if recognizer.AcceptWaveform(data):
                result = json.loads(recognizer.Result())
                if 'text' in result:
                    command = result['text'].lower()
                    print("You said:", command)
                    recognized_text.delete('1.0', END)  # Clear the text field
                    recognized_text.insert(END, "You said: " + command + "\n")  # Update with the latest command
                    # command=input()   #incase unable to listen
                    # Check if the command is to open a web browser
                    if "open website" in command:
                        speak("opening websites")
                        webbrowser.open("https://chat.openai.com/")
                        webbrowser.open("https://gemini.google.com/app")  # Change the URL as needed
                        print("Opening websites...")

                    elif "hello" in command:

                        print("Hello Boss! It's great to see you. How can I help you today?")
                        speak("Hello Boss! It's great to see you. How can I help you today?")

                    elif "you feel" in command:

                        print("Got it, I'm always ready for assistance! What's next?")
                        speak("Got it, I'm always ready for assistance! What's next?")

                    elif "open gym" in command:
                        open_gym()

                    elif "age calculator" in command:
                        agecheck()

                    elif "portfolio" in command:
                        portfolio()

                    elif "what is my i p" in command:

                        ip_details = get_current_ip_details()

                        if ip_details['status'] == 'success':

                            print(f"IP Address: {ip_details['query']}")
                            speak(f"Ip Is: {ip_details['query']}")
                            print(f"Country: {ip_details['country']}")
                            print(f"Region: {ip_details['regionName']}")
                            print(f"City: {ip_details['city']}")
                            print(f"ISP: {ip_details['isp']}")

                            latitude = ip_details['lat']
                            longitude = ip_details['lon']

                            print(f"Latitude: {latitude}")
                            print(f"Longitude: {longitude}")

                        else:
                            speak("Not Fetching Try again Later")
                            print("Failed to fetch IP details.")
                    elif "jojo" in command:
                        try:
                            # Removing the trigger word "jojo" from the command
                            command_without_command = command.replace("jojo", "in one and half line answer").replace(
                                "jojo", "in one and half line answer").strip()

                            speak('Gemini with Joyo Initiated')
                            if is_connected():
                                send_message(command_without_command)  # Sending the modified command without "Friday"

                            else:
                                print("There may be an internet problem. Please check your internet connection.")
                                speak("There may be an internet problem. Please check your internet connection.")
                        except Exception as e:
                            print(e)
                            speak('Sorry, there was an error while running the Gemini program.')


                    elif "restart" in command:
                        restart()
                        break
                    elif "sleep" in command:
                        sleep()
                        break
                    elif "hibernate" in command:
                        hibernate()
                        break

                    elif 'open youtube' in command:
                        webbrowser.open("youtube.com")
                        print("Opening Youtube... ")

                    elif 'open google' in command:
                        webbrowser.open("google.com")
                        print("Opening Google... ")



        except KeyboardInterrupt:
            print("Stopping...")
            break
    stream.stop_stream()
    stream.close()
    audio.terminate()
    listening_active = False


# Function to listen and recognize speech Ends


# TkinterStart Create the main application window
root = Tk()
root.title("JOYO by WAQ-REH-JAV")
root.configure(background="black")


def create_and_animate_plot(canvas):
    fig, ax = plt.subplots(figsize=(4, 3))
    fig.patch.set_facecolor('black')  # Set figure background to black
    ax.set_facecolor('black')  # Set axes background to black
    ax.set_xlim(0, 2 * np.pi)
    ax.set_ylim(-1.5, 1.5)  # Squared waves alternate between -1 and 1
    line1, = ax.plot([], [], lw=5, color='#ADD8E6')  # Light Blue
    line2, = ax.plot([], [], lw=5, color='#FFA500')  # Orange


    ax.set_xticks([])
    ax.set_yticks([])

    def init():
        line1.set_data([], [])
        line2.set_data([], [])
        return line1, line2

    def square_wave(x, phase_shift):
        """Generate a squared waveform with a given phase shift."""
        wave = np.sin(x + phase_shift)
        return np.sign(wave)  # Convert sine wave to square wave

    def animate(i):
        x = np.linspace(0, 2 * np.pi, 100)
        phase_shift_forward = i * np.pi / 5
        phase_shift_reverse = (100 - i) * np.pi / 5

        # Generate forward and reverse square waves
        y1_forward = square_wave(x, phase_shift_forward)
        y2_forward = square_wave(x, -phase_shift_forward)
        y1_reverse = square_wave(x, phase_shift_reverse)
        y2_reverse = square_wave(x, -phase_shift_reverse)

        if i < 50:
            line1.set_data(x, y1_forward)
            line2.set_data(x, y2_forward)
        else:
            line1.set_data(x, y1_reverse)
            line2.set_data(x, y2_reverse)
        return line1, line2
#V2ofadalynn by ar
    animate = FuncAnimation(fig, animate, frames=400, init_func=init, blit=True)
    canvas = tkagg.FigureCanvasTkAgg(fig, master=canvas)
    canvas.draw()
    canvas.get_tk_widget().pack()


# Create a canvas for the plot
plot_canvas = tk.Canvas(root, width=50, height=50)
plot_canvas.pack()

# Call the function to create and animate the plot
create_and_animate_plot(plot_canvas)

# Create a label to display instructions
forSpace = Label(background="black")
forSpace.pack()
labell = Label(root, text="JOYO", font=("Montserrat Black Italic", 22), background="black", foreground="white")
labell.pack()
label2 = Label(root, text="A Virtual Assistant!", font=("Montserrat Black Italic", 11), background="black", foreground="white")
label2.pack()
instruction_label = Label(root, text="Press 'Start' to begin listening.", background="black", foreground="red")
instruction_label.pack()


# Create buttons for starting and stopping the voice recognition process
def start_listening():
    # Use threading to prevent GUI from freezing
    threading.Thread(target=listen_and_recognize, args=(recognized_text,)).start()


#arinRitzGithub: Function to create and animate the plot

# Create a text box to display the recognized text
recognized_text = Text(root, height=2, width=45)
recognized_text.pack()

# 19-apr


# Define custom colors
button_color = "#272633"
button_text_color = "white"

# Create Start button
start_button = tk.Button(root, text="Start", bg=button_color, fg=button_text_color, command=start_listening)
start_button.pack(pady=10)

# Create Stop button
stop_button = tk.Button(root, text="Stop", bg=button_color, fg=button_text_color, command=root.quit)
stop_button.pack(pady=10)

# Start the Tkinter event loop
root.mainloop()
# TkinterEnds