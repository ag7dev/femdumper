import tkinter as tk
from tkinter import scrolledtext, filedialog, messagebox
import customtkinter as ctk
from PIL import Image, ImageTk
import os
import time
import sys
import re
import shutil
import ctypes
import string
import random
import threading
import psutil
import concurrent.futures
import requests
import json
import webbrowser

# Configuration for appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

################## Global Variables #######################
TRIGGER_PATH = "None"
DESKTOP_PATH = os.path.expanduser("~/Desktop")
FEMDUMPER_FOLDER = os.path.join(DESKTOP_PATH, "FemDumper")
os.makedirs(FEMDUMPER_FOLDER, exist_ok=True) if not os.path.exists(FEMDUMPER_FOLDER) else None

ANTICHEAT_KEYWORDS = [
    "Anticheat", "Godmode", "Noclip", "Eulen", "Detection", "Shield", 
    "Fiveguard", "deltax", "waveshield", "spaceshield", "mixas", 
    "protected", "cheater", "cheat", "banNoclip", "Detects", 
    "blacklisted", "CHEATER BANNED:", "core_shield", "freecam"
]
FOLDERS_TO_IGNORE = ["monitor", "easyadmin"]
EXTENSIONS_TO_SEARCH = [".lua", ".html", ".js", ".json"]

class FemDumperApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("FemDumper - Made by FemScripts.de")
        self.geometry("1000x700")
        #self.iconbitmap(self.resource_path("icon.ico")) if os.name == "nt" else None
        
        # Create tab control
        self.tabview = ctk.CTkTabview(self)
        self.tabview.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Add tabs
        self.tabs = {
            "home": self.tabview.add("Home"),
            "triggers": self.tabview.add("Trigger Scanner"),
            "webhooks": self.tabview.add("Webhook Scanner"),
            "anticheat": self.tabview.add("Anticheat Scanner"),
            "variables": self.tabview.add("Variable Scanner"),
            "builder": self.tabview.add("Trigger Builder"),
            "settings": self.tabview.add("Settings")
        }
        
        # Initialize GUI components
        self.init_home_tab()
        self.init_triggers_tab()
        self.init_webhooks_tab()
        self.init_anticheat_tab()
        self.init_variables_tab()
        self.init_builder_tab()
        self.init_settings_tab()
        
        # Status bar
        self.status_var = ctk.StringVar(value="Ready")
        self.status_bar = ctk.CTkLabel(self, textvariable=self.status_var, anchor="w")
        self.status_bar.pack(side="bottom", fill="x", padx=20, pady=5)
        
        # Path monitoring
        self.path_var = ctk.StringVar(value=f"Current Path: {TRIGGER_PATH}")
        self.path_label = ctk.CTkLabel(self, textvariable=self.path_var, anchor="w")
        self.path_label.pack(side="bottom", fill="x", padx=20, pady=5)


    def resource_path(self, relative_path):
        try:
            base_path = sys._MEIPASS
        except Exception:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)

    def init_home_tab(self):
        frame = self.tabs["home"]
        
        # Logo/Banner
        try:
            img = Image.open(self.resource_path("banner.png"))
            img = img.resize((800, 200), Image.LANCZOS)
            banner = ImageTk.PhotoImage(img)
            banner_label = tk.Label(frame, image=banner)
            banner_label.image = banner
            banner_label.pack(pady=20)
        except:
            title = ctk.CTkLabel(frame, text="FemDumper", font=("Arial", 24, "bold"))
            title.pack(pady=20)
        
        # Beschreibung
        desc = ctk.CTkLabel(
            frame, 
            text="Komplettes FiveM Server-Dump Analyse Tool\nErstellt von FemScripts.de",
            font=("Arial", 14)
        )
        desc.pack(pady=10)
        
        # Quick Actions
        actions_frame = ctk.CTkFrame(frame)
        actions_frame.pack(pady=20, fill="x", padx=50)
        
        ctk.CTkButton(
            actions_frame, 
            text="Pfad festlegen",
            command=lambda: self.browse_directory(),
            width=150,
            height=40
        ).pack(side="left", padx=20, pady=10)
        
        ctk.CTkButton(
            actions_frame, 
            text="Alle Scans ausführen",
            command=self.run_all_scans,
            width=150,
            height=40
        ).pack(side="left", padx=20, pady=10)
        
        # Statistik
        stats_frame = ctk.CTkFrame(frame)
        stats_frame.pack(pady=10, fill="x", padx=50)
        
        stats = [
            "Funktionen: Trigger Scanner, Webhook Finder, Anticheat Detection",
            "Export: Alle Ergebnisse werden auf dem Desktop gespeichert",
            "Support: https://femscripts.de"
        ]
        
        for stat in stats:
            ctk.CTkLabel(stats_frame, text=stat, anchor="w").pack(fill="x", padx=20, pady=5)

    def init_triggers_tab(self):
        frame = self.tabs["triggers"]
        
        # Steuerelemente
        ctk.CTkLabel(frame, text="Trigger-Events im Server-Dump suchen", font=("Arial", 16)).pack(pady=10)
        
        btn_frame = ctk.CTkFrame(frame)
        btn_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkButton(
            btn_frame, 
            text="Trigger suchen",
            command=self.find_triggers,
            width=120
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame, 
            text="Ergebnisse exportieren",
            command=lambda: self.open_file(os.path.join(FEMDUMPER_FOLDER, "trigger_events.txt")),
            width=120
        ).pack(side="left", padx=5)
        
        # Ergebnistextbereich
        self.trigger_text = scrolledtext.ScrolledText(frame, height=20)
        self.trigger_text.pack(fill="both", expand=True, padx=20, pady=10)
        self.trigger_text.insert("end", "Trigger-Ergebnisse werden hier angezeigt...")
        self.trigger_text.configure(state="disabled")

    def init_webhooks_tab(self):
        frame = self.tabs["webhooks"]
        
        # Steuerelemente
        ctk.CTkLabel(frame, text="Discord Webhooks im Server-Dump suchen", font=("Arial", 16)).pack(pady=10)
        
        btn_frame = ctk.CTkFrame(frame)
        btn_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkButton(
            btn_frame, 
            text="Webhooks suchen",
            command=self.find_webhooks,
            width=120
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame, 
            text="Webhooks löschen",
            command=self.delete_webhooks,
            width=120
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame, 
            text="Infos anzeigen",
            command=self.show_webhook_info,
            width=120
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame, 
            text="Ergebnisse exportieren",
            command=lambda: self.open_file(os.path.join(FEMDUMPER_FOLDER, "discord_webhooks.txt")),
            width=120
        ).pack(side="left", padx=5)
        
        # Ergebnistextbereich
        self.webhook_text = scrolledtext.ScrolledText(frame, height=20)
        self.webhook_text.pack(fill="both", expand=True, padx=20, pady=10)
        self.webhook_text.insert("end", "Webhook-Ergebnisse werden hier angezeigt...")
        self.webhook_text.configure(state="disabled")

    def init_anticheat_tab(self):
        frame = self.tabs["anticheat"]
        
        # Steuerelemente
        ctk.CTkLabel(frame, text="Anticheat-Systeme im Server-Dump erkennen", font=("Arial", 16)).pack(pady=10)
        
        btn_frame = ctk.CTkFrame(frame)
        btn_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkButton(
            btn_frame, 
            text="Keywords suchen",
            command=self.find_anticheat_keywords,
            width=140
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame, 
            text="Bekannte ACs suchen",
            command=self.find_known_anticheats,
            width=140
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame, 
            text="Ergebnisse exportieren",
            command=lambda: self.open_file(os.path.join(FEMDUMPER_FOLDER, "anticheat_results.txt")),
            width=140
        ).pack(side="left", padx=5)
        
        # Ergebnistextbereich
        self.anticheat_text = scrolledtext.ScrolledText(frame, height=20)
        self.anticheat_text.pack(fill="both", expand=True, padx=20, pady=10)
        self.anticheat_text.insert("end", "Anticheat-Ergebnisse werden hier angezeigt...")
        self.anticheat_text.configure(state="disabled")
        
        # Keyword-Liste
        keyword_frame = ctk.CTkFrame(frame)
        keyword_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(keyword_frame, text="Aktive Keywords:").pack(anchor="w", padx=10, pady=5)
        keyword_text = ", ".join(ANTICHEAT_KEYWORDS[:10]) + "..."
        ctk.CTkLabel(keyword_frame, text=keyword_text, wraplength=800).pack(fill="x", padx=10, pady=5)

    def init_variables_tab(self):
        frame = self.tabs["variables"]
        
        # Steuerelemente
        ctk.CTkLabel(frame, text="Besondere Variablen im Server-Dump finden", font=("Arial", 16)).pack(pady=10)
        
        btn_frame = ctk.CTkFrame(frame)
        btn_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkButton(
            btn_frame, 
            text="Variablen suchen",
            command=self.find_variables,
            width=120
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame, 
            text="Ergebnisse exportieren",
            command=lambda: self.open_file(os.path.join(FEMDUMPER_FOLDER, "variables.txt")),
            width=120
        ).pack(side="left", padx=5)
        
        # Ergebnistextbereich
        self.variable_text = scrolledtext.ScrolledText(frame, height=20)
        self.variable_text.pack(fill="both", expand=True, padx=20, pady=10)
        self.variable_text.insert("end", "Variablen-Ergebnisse werden hier angezeigt...")
        self.variable_text.configure(state="disabled")

    def init_builder_tab(self):
        frame = self.tabs["builder"]
        
        # Trigger-Builder UI
        ctk.CTkLabel(frame, text="FiveM Trigger Event Builder", font=("Arial", 16)).pack(pady=10)
        
        form_frame = ctk.CTkFrame(frame)
        form_frame.pack(fill="x", padx=20, pady=10)
        
        # Event-Typ
        ctk.CTkLabel(form_frame, text="Event-Typ:").grid(row=0, column=0, padx=5, pady=5, sticky="w")
        self.event_type = ctk.StringVar(value="server")
        ctk.CTkRadioButton(form_frame, text="Server Event", variable=self.event_type, value="server").grid(row=0, column=1, padx=5, pady=5)
        ctk.CTkRadioButton(form_frame, text="Client Event", variable=self.event_type, value="client").grid(row=0, column=2, padx=5, pady=5)
        
        # Event-Name
        ctk.CTkLabel(form_frame, text="Event-Name:").grid(row=1, column=0, padx=5, pady=5, sticky="w")
        self.event_name = ctk.CTkEntry(form_frame, width=300)
        self.event_name.grid(row=1, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        
        # Parameter
        ctk.CTkLabel(form_frame, text="Parameter (kommagetrennt):").grid(row=2, column=0, padx=5, pady=5, sticky="w")
        self.event_params = ctk.CTkEntry(form_frame, width=300)
        self.event_params.grid(row=2, column=1, columnspan=2, padx=5, pady=5, sticky="ew")
        
        # Code-Vorschau
        ctk.CTkLabel(frame, text="Trigger-Code:").pack(anchor="w", padx=25, pady=(10, 0))
        self.code_preview = scrolledtext.ScrolledText(frame, height=8)
        self.code_preview.pack(fill="x", padx=20, pady=5)
        self.code_preview.configure(state="normal")
        self.code_preview.insert("end", "Hier wird Ihr generierter Code angezeigt...")
        self.code_preview.configure(state="disabled")
        
        # Aktualisierungs-Button
        ctk.CTkButton(
            frame, 
            text="Code generieren",
            command=self.generate_trigger_code,
            width=120
        ).pack(pady=5)
        
        # Speicher-Button
        btn_frame = ctk.CTkFrame(frame)
        btn_frame.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkButton(
            btn_frame, 
            text="Code speichern",
            command=self.save_trigger_code,
            width=120
        ).pack(side="left", padx=5)

    def init_settings_tab(self):
        frame = self.tabs["settings"]
        
        # Pfadeinstellungen
        ctk.CTkLabel(frame, text="Server-Dump Pfad", font=("Arial", 14)).pack(anchor="w", padx=20, pady=(20, 5))
        
        path_frame = ctk.CTkFrame(frame)
        path_frame.pack(fill="x", padx=20, pady=5)
        
        self.path_entry = ctk.CTkEntry(path_frame)
        self.path_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        self.path_entry.insert(0, TRIGGER_PATH)
        
        ctk.CTkButton(
            path_frame, 
            text="Durchsuchen",
            command=self.browse_directory,
            width=100
        ).pack(side="right")
        
        ctk.CTkButton(
            frame, 
            text="Pfad speichern",
            command=self.save_path,
            width=120
        ).pack(anchor="e", padx=20, pady=5)
        
        # Optionen
        ctk.CTkLabel(frame, text="Erweiterte Optionen", font=("Arial", 14)).pack(anchor="w", padx=20, pady=(20, 5))
        
        option_frame = ctk.CTkFrame(frame)
        option_frame.pack(fill="x", padx=20, pady=5)
        
        self.auto_save = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            option_frame, 
            text="Ergebnisse automatisch speichern",
            variable=self.auto_save
        ).pack(anchor="w", padx=10, pady=5)
        
        # Info
        ctk.CTkLabel(frame, text="Support & Informationen", font=("Arial", 14)).pack(anchor="w", padx=20, pady=(20, 5))
        
        info_frame = ctk.CTkFrame(frame)
        info_frame.pack(fill="x", padx=20, pady=5)
        
        ctk.CTkButton(
            info_frame, 
            text="Dokumentation öffnen",
            command=lambda: webbrowser.open("https://femscripts.de/docs"),
            width=150
        ).pack(side="left", padx=5, pady=5)
        
        ctk.CTkButton(
            info_frame, 
            text="GitHub Repository",
            command=lambda: webbrowser.open("https://github.com/femscripts/femdumper"),
            width=150
        ).pack(side="left", padx=5, pady=5)

    def browse_directory(self):
        global TRIGGER_PATH
        path = filedialog.askdirectory(title="Server-Dump Ordner auswählen")
        if path:
            TRIGGER_PATH = path
            self.path_var.set(f"Aktueller Pfad: {TRIGGER_PATH}")
            self.path_entry.delete(0, "end")
            self.path_entry.insert(0, TRIGGER_PATH)
            self.update_status("Pfad erfolgreich festgelegt")

    def save_path(self):
        global TRIGGER_PATH
        TRIGGER_PATH = self.path_entry.get()
        self.path_var.set(f"Aktueller Pfad: {TRIGGER_PATH}")
        self.update_status("Pfad erfolgreich gespeichert")

    def update_status(self, message):
        self.status_var.set(message)
        self.after(5000, lambda: self.status_var.set("Bereit") if message != "Bereit" else None)

    def open_file(self, filepath):
        if os.path.exists(filepath):
            os.startfile(filepath) if os.name == "nt" else None
        else:
            messagebox.showwarning("Datei nicht gefunden", "Die angeforderte Datei existiert nicht.")

    def validate_path(self):
        if TRIGGER_PATH == "None" or not os.path.exists(TRIGGER_PATH):
            messagebox.showerror("Ungültiger Pfad", "Bitte setzen Sie zuerst einen gültigen Pfad!")
            return False
        return True

    def run_all_scans(self):
        if not self.validate_path():
            return
            
        threading.Thread(target=self.find_triggers).start()
        threading.Thread(target=self.find_webhooks).start()
        threading.Thread(target=self.find_anticheat_keywords).start()
        threading.Thread(target=self.find_variables).start()
        self.update_status("Alle Scans gestartet...")

    def find_triggers(self):
        if not self.validate_path():
            return
            
        self.update_status("Suche Trigger-Events...")
        output_file = os.path.join(FEMDUMPER_FOLDER, "trigger_events.txt")
        trigger_events = []
        
        try:
            for root, dirs, files in os.walk(TRIGGER_PATH):
                for filename in files:
                    if filename.endswith(".lua"):
                        file_path = os.path.join(root, filename)
                        folder_name = os.path.basename(os.path.dirname(file_path))
                        try:
                            with open(file_path, "r", encoding="latin-1") as file:
                                for line_number, line in enumerate(file, start=1):
                                    if re.search(r"\b(TriggerServerEvent|TriggerEvent)\b", line):
                                        trigger_events.append((folder_name, line_number, line.strip()))
                        except Exception:
                            continue
            
            with open(output_file, "w", encoding="utf-8") as output:
                for event in trigger_events:
                    output.write(f"\n{'='*25} [{event[0]} - Line {event[1]}] {'='*25}\n")
                    output.write(f"{event[2]}\n")
            
            # Ergebnisse in der GUI anzeigen
            self.trigger_text.configure(state="normal")
            self.trigger_text.delete(1.0, "end")
            for event in trigger_events[:100]:  # Begrenzung auf 100 Einträge für die Anzeige
                self.trigger_text.insert("end", f"[{event[0]}] Line {event[1]}: {event[2]}\n")
            self.trigger_text.configure(state="disabled")
            
            self.update_status(f"Trigger-Scan abgeschlossen! {len(trigger_events)} Events gefunden")
        except Exception as e:
            self.update_status(f"Fehler: {str(e)}")
            messagebox.showerror("Fehler", f"Ein Fehler ist aufgetreten: {str(e)}")

    def find_webhooks(self):
        if not self.validate_path():
            return
            
        self.update_status("Suche Discord Webhooks...")
        output_file = os.path.join(FEMDUMPER_FOLDER, "discord_webhooks.txt")
        webhook_urls = []
        webhook_pattern = re.compile(r"https://discord\.com/api/webhooks/\w+/\w+")
        
        def is_webhook_valid(url):
            try:
                response = requests.get(url, timeout=5)
                return response.status_code == 200
            except requests.RequestException:
                return False
        
        try:
            for root, dirs, files in os.walk(TRIGGER_PATH):
                for filename in files:
                    full_path = os.path.join(root, filename)
                    if os.path.isfile(full_path):
                        try:
                            with open(full_path, "r", encoding="utf-8", errors="ignore") as file:
                                content = file.read()
                                matches = webhook_pattern.findall(content)
                                for match in matches:
                                    if is_webhook_valid(match):
                                        webhook_urls.append((full_path, match))
                        except Exception:
                            continue
            
            with open(output_file, "w", encoding="utf-8") as output:
                output.write(f"File Path{' ' * 55}| Webhook URL\n")
                output.write(f"{'-'*80}\n")
                for webhook_url in webhook_urls:
                    output.write(f"{webhook_url[0]:<60} | {webhook_url[1]}\n")
            
            # Ergebnisse in der GUI anzeigen
            self.webhook_text.configure(state="normal")
            self.webhook_text.delete(1.0, "end")
            for webhook in webhook_urls[:50]:  # Begrenzung auf 50 Einträge für die Anzeige
                self.webhook_text.insert("end", f"File: {webhook[0]}\nWebhook: {webhook[1]}\n\n")
            self.webhook_text.configure(state="disabled")
            
            self.update_status(f"Webhook-Scan abgeschlossen! {len(webhook_urls)} gültige Webhooks gefunden")
        except Exception as e:
            self.update_status(f"Fehler: {str(e)}")
            messagebox.showerror("Fehler", f"Ein Fehler ist aufgetreten: {str(e)}")

    def delete_webhooks(self):
        if not messagebox.askyesno("Bestätigung", "Möchten Sie wirklich alle gefundenen Webhooks löschen?"):
            return
            
        self.update_status("Lösche Webhooks...")
        webhook_file = os.path.join(FEMDUMPER_FOLDER, "discord_webhooks.txt")
        
        try:
            if not os.path.exists(webhook_file):
                messagebox.showwarning("Datei nicht gefunden", "Webhook-Datei existiert nicht.")
                return
                
            with open(webhook_file, "r", encoding="utf-8") as file:
                lines = file.readlines()
                webhooks = []
                for line in lines[2:]:  # Header überspringen
                    if "|" in line:
                        webhooks.append(line.split("|")[1].strip())
            
            for url in webhooks:
                try:
                    response = requests.delete(url, timeout=5)
                    if response.status_code == 204:
                        self.update_status(f"Gelöscht: {url}")
                except requests.RequestException as e:
                    self.update_status(f"Fehler beim Löschen: {str(e)}")
            
            self.update_status("Webhook-Löschung abgeschlossen!")
        except Exception as e:
            self.update_status(f"Fehler: {str(e)}")
            messagebox.showerror("Fehler", f"Ein Fehler ist aufgetreten: {str(e)}")

    def show_webhook_info(self):
        webhook_file = os.path.join(FEMDUMPER_FOLDER, "discord_webhooks.txt")
        
        try:
            if not os.path.exists(webhook_file):
                messagebox.showwarning("Datei nicht gefunden", "Webhook-Datei existiert nicht.")
                return
                
            with open(webhook_file, "r", encoding="utf-8") as file:
                lines = file.readlines()
                webhooks = []
                for line in lines[2:]:
                    if "|" in line:
                        webhooks.append(line.split("|")[1].strip())
            
            info_window = ctk.CTkToplevel(self)
            info_window.title("Webhook Informationen")
            info_window.geometry("600x400")
            
            text_area = scrolledtext.ScrolledText(info_window, wrap="word")
            text_area.pack(fill="both", expand=True, padx=10, pady=10)
            
            for url in webhooks:
                try:
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        data = response.json()
                        text_area.insert("end", f"URL: {url}\n")
                        text_area.insert("end", json.dumps(data, indent=4) + "\n\n")
                except requests.RequestException as e:
                    text_area.insert("end", f"Fehler bei {url}: {str(e)}\n\n")
            
            text_area.configure(state="disabled")
        except Exception as e:
            messagebox.showerror("Fehler", f"Ein Fehler ist aufgetreten: {str(e)}")

    def find_anticheat_keywords(self):
        if not self.validate_path():
            return
            
        self.update_status("Suche nach Anticheat-Keywords...")
        output_file = os.path.join(FEMDUMPER_FOLDER, "anticheat_keywords.txt")
        found_entries = []
        
        try:
            for root, dirs, files in os.walk(TRIGGER_PATH):
                for folder in FOLDERS_TO_IGNORE:
                    if folder in dirs:
                        dirs.remove(folder)
                
                for filename in files:
                    if any(filename.endswith(ext) for ext in EXTENSIONS_TO_SEARCH):
                        file_path = os.path.join(root, filename)
                        folder_name = os.path.basename(os.path.dirname(file_path))
                        try:
                            with open(file_path, "r", encoding="latin-1") as file:
                                for line_number, line in enumerate(file, start=1):
                                    for keyword in ANTICHEAT_KEYWORDS:
                                        if keyword in line:
                                            found_entries.append((folder_name, line_number, line.strip()))
                        except Exception:
                            continue
            
            with open(output_file, "w", encoding="utf-8") as output:
                for entry in found_entries:
                    output.write(f"[{entry[0]}] - [Line {entry[1]}] {entry[2]}\n")
            
            # Ergebnisse in der GUI anzeigen
            self.anticheat_text.configure(state="normal")
            self.anticheat_text.delete(1.0, "end")
            for entry in found_entries[:100]:  # Begrenzung auf 100 Einträge
                self.anticheat_text.insert("end", f"[{entry[0]}] Line {entry[1]}: {entry[2]}\n")
            self.anticheat_text.configure(state="disabled")
            
            self.update_status(f"Anticheat-Keyword-Suche abgeschlossen! {len(found_entries)} Treffer gefunden")
        except Exception as e:
            self.update_status(f"Fehler: {str(e)}")
            messagebox.showerror("Fehler", f"Ein Fehler ist aufgetreten: {str(e)}")

    def find_known_anticheats(self):
        if not self.validate_path():
            return
            
        self.update_status("Suche nach bekannten Anticheats...")
        output_file = os.path.join(FEMDUMPER_FOLDER, "known_anticheats.txt")
        ac_detections = []
        ac_files = {
            "shared_fg-obfuscated.lua": "FiveGuard",
            "fini_events.lua": "FiniAC",
            "c-bypass.lua": "Reaper-AC",
            "waveshield.lua": "WaveShield"
        }
        
        try:
            for file_to_check, detection_name in ac_files.items():
                for root, dirs, files in os.walk(TRIGGER_PATH):
                    for filename in files:
                        if filename == file_to_check:
                            folder_name = os.path.basename(root)
                            ac_detections.append(f"{detection_name} detected in {folder_name}")
            
            with open(output_file, "w", encoding="utf-8") as output:
                for detection in ac_detections:
                    output.write(f"{detection}\n")
            
            # Ergebnisse in der GUI anzeigen
            self.anticheat_text.configure(state="normal")
            self.anticheat_text.delete(1.0, "end")
            for detection in ac_detections:
                self.anticheat_text.insert("end", f"{detection}\n")
            self.anticheat_text.configure(state="disabled")
            
            self.update_status(f"Bekannte Anticheat-Suche abgeschlossen! {len(ac_detections)} Treffer gefunden")
        except Exception as e:
            self.update_status(f"Fehler: {str(e)}")
            messagebox.showerror("Fehler", f"Ein Fehler ist aufgetreten: {str(e)}")

    def find_variables(self):
        if not self.validate_path():
            return
            
        self.update_status("Suche nach speziellen Variablen...")
        output_file = os.path.join(FEMDUMPER_FOLDER, "variables.txt")
        variables_list = []
        
        try:
            for root, dirs, files in os.walk(TRIGGER_PATH):
                for filename in files:
                    if filename.endswith(".lua"):
                        file_path = os.path.join(root, filename)
                        folder_name = os.path.basename(os.path.dirname(file_path))
                        try:
                            with open(file_path, "r", encoding="latin-1") as file:
                                for line_number, line in enumerate(file, start=1):
                                    if re.search(r'\bvar_\w+\b', line):
                                        variables_list.append((folder_name, line_number, line.strip()))
                        except Exception:
                            continue
            
            with open(output_file, "a", encoding="utf-8") as output:
                output.write("\nVariables:\n")
                for variable in variables_list:
                    output.write(f"[{variable[0]}] - [Line {variable[1]}] {variable[2]}\n")
            
            # Ergebnisse in der GUI anzeigen
            self.variable_text.configure(state="normal")
            self.variable_text.delete(1.0, "end")
            for variable in variables_list[:100]:  # Begrenzung auf 100 Einträge
                self.variable_text.insert("end", f"[{variable[0]}] Line {variable[1]}: {variable[2]}\n")
            self.variable_text.configure(state="disabled")
            
            self.update_status(f"Variablen-Suche abgeschlossen! {len(variables_list)} Variablen gefunden")
        except Exception as e:
            self.update_status(f"Fehler: {str(e)}")
            messagebox.showerror("Fehler", f"Ein Fehler ist aufgetreten: {str(e)}")

    def generate_trigger_code(self):
        event_type = self.event_type.get()
        event_name = self.event_name.get()
        params = self.event_params.get().split(",") if self.event_params.get() else []
        
        if not event_name:
            messagebox.showwarning("Fehlende Information", "Bitte geben Sie einen Event-Namen ein!")
            return
            
        # Code generieren
        param_string = ", ".join([f'"{p.strip()}"' for p in params if p.strip()])
        
        if event_type == "server":
            code = f"TriggerServerEvent('{event_name}'"
        else:
            code = f"TriggerEvent('{event_name}'"
        
        if param_string:
            code += f", {param_string}"
        
        code += ")"
        
        # Code in Vorschau anzeigen
        self.code_preview.configure(state="normal")
        self.code_preview.delete(1.0, "end")
        self.code_preview.insert("end", code)
        self.code_preview.configure(state="disabled")

    def save_trigger_code(self):
        code = self.code_preview.get(1.0, "end-1c")
        if not code or code == "Hier wird Ihr generierter Code angezeigt...":
            messagebox.showwarning("Kein Code", "Es wurde kein Code zum Speichern generiert!")
            return
            
        file_path = filedialog.asksaveasfilename(
            defaultextension=".lua",
            filetypes=[("Lua Dateien", "*.lua"), ("Alle Dateien", "*.*")],
            title="Trigger-Code speichern"
        )
        
        if file_path:
            try:
                with open(file_path, "w", encoding="utf-8") as file:
                    file.write(f"-- Generated by FemDumper\n{code}")
                self.update_status("Trigger-Code erfolgreich gespeichert!")
            except Exception as e:
                messagebox.showerror("Speichern fehlgeschlagen", f"Fehler: {str(e)}")

    def on_closing(self):
        if messagebox.askokcancel("Beenden", "Möchten Sie FemDumper wirklich beenden?"):
            self.destroy()
            sys.exit()

if __name__ == "__main__":
    # Ordner für Ergebnisse sicherstellen
    if not os.path.exists(FEMDUMPER_FOLDER):
        os.makedirs(FEMDUMPER_FOLDER)
    
    app = FemDumperApp()
    app.protocol("WM_DELETE_WINDOW", app.on_closing)
    app.mainloop()