#!/usr/bin/env python3
"""JOYOP voice-controlled assistant with a local audio website."""

from __future__ import annotations

import functools
import json
import os
import platform
import shutil
import subprocess
import sys
import threading
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import numpy as np
import pyttsx3
import requests
import tkinter as tk
import tkinter.ttk as ttk
from matplotlib import animation, pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

try:
    import pyaudio
    import vosk
except ImportError as exc:  # pragma: no cover - environment-specific
    pyaudio = None
    vosk = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

ROOT = Path(__file__).resolve().parent
MODEL_DIR = ROOT.parent / "models" / "vosk-model-en-in-0.5"
SITE_FILE = ROOT / "audio_assistant.html"
PORT = int(os.environ.get("JOYOP_PORT", "8765"))
API_URL = f"http://127.0.0.1:{PORT}"

engine = pyttsx3.init()
engine.setProperty("rate", 150)
engine.setProperty("volume", 1.0)


def speak(text: str) -> None:
    """Speak text through the installed system TTS engine."""
    print(f"JOYOP: {text}")
    if not text:
        return
    engine.say(text)
    engine.runAndWait()


def current_os() -> str:
    return platform.system().lower()


def _run(command: list[str], *, timeout: float | None = 5.0) -> subprocess.CompletedProcess[Any]:
    return subprocess.run(command, capture_output=True, text=True, timeout=timeout, check=False)


def find_executable(*names: str) -> str | None:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def open_url(url: str) -> bool:
    try:
        webbrowser.open(url, new=2, autoraise=True)
        return True
    except Exception as exc:
        print(f"Could not open URL: {exc}")
        return False


def open_file_manager() -> bool:
    system = current_os()
    candidates = {
        "windows": (["explorer.exe", "."],),
        "darwin": (["open", "."],),
        "linux": (["xdg-open", "/"], ["nautilus", "/"], ["thunar", "/"], ["pcmanfm-qt", "/"]),
    }
    for command in candidates.get(system, ()):
        executable = find_executable(command[0])
        if executable:
            try:
                subprocess.Popen([executable, *command[1:]], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
                return True
            except OSError:
                continue
    return False


def launch_application(names: tuple[str, ...]) -> bool:
    executable = find_executable(*names)
    if executable is None:
        return False
    try:
        subprocess.Popen([executable], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        return True
    except OSError:
        return False


def open_terminal() -> bool:
    return launch_application(("gnome-terminal", "xfce4-terminal", "konsole", "qterminal", "tilix"))


def open_calculator() -> bool:
    return launch_application(("gnome-calculator", "kcalc", "qcalculator", "mate-calc"))


def open_settings() -> bool:
    return launch_application(("gnome-control-center", "kde-gtk-config", "mate-control-center"))


def open_text_editor() -> bool:
    return launch_application(("code", "gedit", "notepad", "kate"))


def action_for_command(command: str) -> tuple[str, str | None]:
    normalized = command.strip().lower()
    urls = {
        "open google": "https://www.google.com",
        "open youtube": "https://www.youtube.com",
        "open gym": "https://gym-website-muhammad-shafiullah.netlify.app",
        "open age calculator": "https://checkyourage.netlify.app",
        "open portfolio": "https://ahsanrazabaloch.netlify.app",
        "open website": f"{API_URL}/audio_assistant.html",
        "open audio site": f"{API_URL}/audio_assistant.html",
        "open chat gpt": "https://chatgpt.com",
        "open gemini": "https://gemini.google.com/app",
    }
    for phrase, url in urls.items():
        if phrase in normalized:
            return "open", url

    if any(phrase in normalized for phrase in ("file manager", "file explorer", "open file manager", "open file explorer")):
        return "file_manager", None
    if any(phrase in normalized for phrase in ("open terminal", "command prompt", "terminal")):
        return "terminal", None
    if any(phrase in normalized for phrase in ("open calculator", "calculator")):
        return "calculator", None
    if any(phrase in normalized for phrase in ("open settings", "control panel", "settings")):
        return "settings", None
    if any(phrase in normalized for phrase in ("open code editor", "open editor", "code editor", "editor")):
        return "editor", None
    if "stop listening" in normalized:
        return "stop_listening", None
    if "hello" in normalized or "hi jojo" in normalized:
        return "greeting", None
    if "what is my ip" in normalized or "my ip address" in normalized:
        return "ip", None
    return "unknown", None


def get_public_ip() -> dict[str, Any]:
    response = requests.get("https://api.ipify.org?format=json", timeout=10)
    response.raise_for_status()
    return response.json()


class AudioSiteHandler(BaseHTTPRequestHandler):
    server_version = "JOYOP/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        print("[site] " + (format % args))

    def do_GET(self) -> None:
        if self.path not in ("/", "/index.html", "/audio_assistant.html"):
            self.send_error(404)
            return
        body = SITE_FILE.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self) -> None:
        if self.path != "/api/command":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8", errors="replace"))
        command = payload.get("command", "")
        response = execute_command(command, source="site")
        body = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class VoiceController:
    def __init__(self) -> None:
        self.running = False
        self.listening = False
        self.recognizer: Any = None
        self.audio: Any = None
        self.stream: Any = None
        self.server: ThreadingHTTPServer | None = None
        self.server_thread: threading.Thread | None = None
        self.site_url = f"http://127.0.0.1:{PORT}/audio_assistant.html"

    def start_server(self) -> None:
        if self.server is not None:
            return
        self.server = ThreadingHTTPServer(("127.0.0.1", PORT), AudioSiteHandler)
        self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.server_thread.start()
        open_url(self.site_url)

    def stop_server(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.server = None
        if self.server_thread is not None:
            self.server_thread.join(timeout=2)
            self.server_thread = None

    def _initialize_vosk(self) -> bool:
        if vosk is None or pyaudio is None:
            print(f"Optional voice stack unavailable: {_IMPORT_ERROR}")
            return False
        if not MODEL_DIR.is_dir():
            print(f"Vosk model not found: {MODEL_DIR}")
            return False
        try:
            model = vosk.Model(str(MODEL_DIR))
            self.recognizer = vosk.KaldiRecognizer(model, 16000)
            self.audio = pyaudio.PyAudio()
            return True
        except Exception as exc:
            print(f"Could not initialize speech recognition: {exc}")
            return False

    def stop_listening(self) -> None:
        self.listening = False
        if self.stream is not None:
            try:
                self.stream.stop_stream()
            except Exception:
                pass
            try:
                self.stream.close()
            except Exception:
                pass
        if self.audio is not None:
            try:
                self.audio.terminate()
            except Exception:
                pass
        if self.recognizer is not None:
            self.recognizer = None

    def listen(self) -> None:
        if self.listening:
            return
        if not self._initialize_vosk():
            return
        self.listening = True
        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=16000,
            input=True,
            frames_per_buffer=8000,
        )
        print("Listening for commands...")
        while self.listening:
            try:
                data = self.stream.read(8000)
                if not self.recognizer.AcceptWaveform(data):
                    continue
                result = json.loads(self.recognizer.Result())
                if "text" not in result:
                    continue
                execute_command(result["text"], source="voice")
                if result["text"].lower() in {"stop listening", "end listening"}:
                    self.stop_listening()
                    break
            except (KeyboardInterrupt, OSError) as exc:
                print(f"Listening stopped: {exc}")
                break
        self.stop_listening()

    def execute_basic_command(self, command: str) -> dict[str, Any]:
        return execute_command(command, source="gui")


def execute_command(command: str, *, source: str) -> dict[str, Any]:
    text = command.strip().lower()
    print(f"[{source}] {text}")
    if not text:
        return {"message": "I did not understand that command.", "speech": "I did not understand that command."}

    action, target = action_for_command(text)
    if action == "open" and target:
        open_url(target)
        speak(f"Opened {target}")
        return {"message": f"Opened {target}", "speech": f"Opened {target}", "url": target}

    if action == "file_manager":
        if open_file_manager():
            return {"message": "File manager opened.", "speech": "File manager opened."}
        return {"message": "Could not open the file manager.", "speech": "Could not open the file manager."}

    if action == "terminal":
        if open_terminal():
            return {"message": "Terminal opened.", "speech": "Terminal opened."}
        return {"message": "No terminal application was found.", "speech": "No terminal application was found."}

    if action == "calculator":
        if open_calculator():
            return {"message": "Calculator opened.", "speech": "Calculator opened."}
        return {"message": "No calculator application was found.", "speech": "No calculator application was found."}

    if action == "settings":
        if open_settings():
            return {"message": "Settings opened.", "speech": "Settings opened."}
        return {"message": "No settings application was found.", "speech": "No settings application was found."}

    if action == "editor":
        if open_text_editor():
            return {"message": "Text editor opened.", "speech": "Text editor opened."}
        return {"message": "No text editor was found.", "speech": "No text editor was found."}

    if action == "stop_listening":
        return {"message": "Listening stopped.", "speech": "Listening stopped."}

    if action == "greeting":
        response = "Hello! I am JOYOP, your voice assistant. How can I help you today?"
        speak(response)
        return {"message": response, "speech": response}

    if action == "ip":
        try:
            data = get_public_ip()
            response = f"Your public IP address is {data.get('ip', 'unknown')}."
            speak(response)
            return {"message": response, "speech": response}
        except Exception as exc:
            response = "Could not retrieve your IP address. Please check your internet connection."
            speak(response)
            return {"message": response, "speech": response, "error": str(exc)}

    if "search for " in text:
        query = text.removeprefix("search for ").strip()
        url = f"https://www.google.com/search?q={requests.utils.quote(query)}"
        open_url(url)
        return {"message": f"Searching for {query}.", "speech": f"Searching for {query}.", "url": url}

    response = "I did not understand that command. Try: open file manager, open terminal, open calculator, open settings, open Google, open YouTube, open audio site, or what is my IP."
    speak(response)
    return {"message": response, "speech": response}


class JOYOWindow:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title("JOYOP Voice Assistant")
        self.root.geometry("460x620")
        self.root.configure(bg="#11111a")
        self.controller = VoiceController()
        self.controller.start_server()
        self.build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.mainloop()

    def build_ui(self) -> None:
        frame = ttk.Frame(self.root, padding=20)
        frame.grid(row=0, column=0, sticky="nsew")
        ttk.Label(frame, text="JOYOP", font=("Arial", 28, "bold")).grid(sticky="w")
        ttk.Label(frame, text="Voice-controlled assistant", foreground="#8fe3ff").grid(sticky="w", pady=(0, 18))
        self.status = ttk.Label(frame, text="Ready", foreground="#91e6bd")
        self.status.grid(sticky="w", pady=(0, 8))
        self.command_text = tk.Text(frame, height=3, wrap="word", bg="#1b1b28", fg="white", relief="flat")
        self.command_text.grid(sticky="ew", pady=(0, 8))
        ttk.Button(frame, text="Start listening", command=self.start_listening).grid(sticky="ew", pady=(0, 8))
        ttk.Button(frame, text="Open audio site", command=self.open_audio_site).grid(sticky="ew", pady=(0, 8))
        ttk.Button(frame, text="Open file manager", command=self.open_file_manager).grid(sticky="ew", pady=(0, 8))
        ttk.Button(frame, text="Open terminal", command=self.open_terminal).grid(sticky="ew", pady=(0, 8))
        ttk.Button(frame, text="Stop", command=self.close).grid(sticky="ew", pady=(0, 8))
        for label, text in [
            ("Open Google", "Open Google"),
            ("Open YouTube", "Open YouTube"),
            ("Open calculator", "Open calculator"),
            ("Open settings", "Open settings"),
            ("What is my IP", "What is my IP"),
        ]:
            ttk.Button(frame, text=label, command=lambda value=text: self.run_command(value)).grid(sticky="ew", pady=(0, 4))
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

    def run_command(self, command: str) -> None:
        result = execute_command(command, source="gui")
        self.command_text.delete("1.0", tk.END)
        self.command_text.insert(tk.END, result["message"])
        self.status.configure(text="Command complete", foreground="#91e6bd")

    def start_listening(self) -> None:
        self.status.configure(text="Listening…", foreground="#ffb5c5")
        thread = threading.Thread(target=self.controller.listen, daemon=True)
        thread.start()

    def open_audio_site(self) -> None:
        self.controller.start_server()
        open_url(self.controller.site_url)
        self.run_command("open audio site")

    def open_file_manager(self) -> None:
        self.run_command("open file manager")

    def open_terminal(self) -> None:
        self.run_command("open terminal")

    def close(self) -> None:
        self.controller.stop_listening()
        self.controller.stop_server()
        self.root.destroy()


def main() -> None:
    if not SITE_FILE.exists():
        raise FileNotFoundError(f"Audio site not found: {SITE_FILE}")
    if not MODEL_DIR.is_dir():
        print(f"Warning: Vosk model not found. Voice recognition disabled: {MODEL_DIR}")
    print(f"Opening audio site: {API_URL}/audio_assistant.html")
    JOYOWindow()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("JOYOP stopped.")
