
import os
import sys
import re
import threading
import time
import shutil
import json
import random
import string
import ctypes
import psutil
import concurrent.futures
import requests
import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox

# Initialize customtkinter
ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class FemDumperApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("FemDumper GUI")
        self.geometry("1000x700")

        # Prepare output directory on Desktop
        self.desktop = os.path.expanduser("~/Desktop")
        self.output_dir = os.path.join(self.desktop, "FemDumper")
        if os.path.exists(self.output_dir):
            shutil.rmtree(self.output_dir)
        os.makedirs(self.output_dir, exist_ok=True)

        # State
        self.trigger_path = None
        self.anticheat_keywords = [
            "Anticheat", "Godmode", "Noclip", "Eulen", "Detection", "Shield",
            "Fiveguard", "deltax", "waveshield", "spaceshield", "mixas",
            "protected", "cheater", "cheat", "banNoclip", "Detects",
            "blacklisted", "CHEATER BANNED:", "core_shield", "freecam"
        ]
        self.ac_files_map = {
            "shared_fg-obfuscated.lua": "FiveGuard",
            "fini_events.lua": "FiniAC",
            "c-bypass.lua": "Reaper-AC",
            "waveshield.lua": "WaveShield"
        }
        self.folders_to_ignore = ["monitor", "easyadmin"]
        self.extensions_to_search = [".lua", ".html", ".js", ".json"]

        # Build GUI
        self.tabview = ctk.CTkTabview(self, width=950, height=600)
        self.tabview.pack(padx=20, pady=20, fill="both", expand=True)
        tabs = ["Select Path", "Triggers", "Webhooks", "Anticheat", "Variables", "Trigger Builder", "Settings"]
        for tab in tabs: self.tabview.add(tab)
        self.build_select_tab()
        self.build_triggers_tab()
        self.build_webhooks_tab()
        self.build_anticheat_tab()
        self.build_variables_tab()
        self.build_builder_tab()
        self.build_settings_tab()

    def build_select_tab(self):
        tab = self.tabview.tab("Select Path")
        btn = ctk.CTkButton(tab, text="Choose Server Dump Folder", command=self.select_folder)
        btn.pack(pady=40)
        self.lbl_path = ctk.CTkLabel(tab, text="No folder selected.")
        self.lbl_path.pack(pady=10)

    def select_folder(self):
        path = filedialog.askdirectory()
        if path and os.path.isdir(path) and os.listdir(path):
            self.trigger_path = path
            self.lbl_path.configure(text=path)
        else:
            messagebox.showerror("Error", "Invalid or empty folder selected.")

    def build_triggers_tab(self):
        tab = self.tabview.tab("Triggers")
        frame = ctk.CTkFrame(tab); frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.txt_triggers = ctk.CTkTextbox(frame); self.txt_triggers.pack(fill="both", expand=True)
        ctk.CTkButton(frame, text="Find Triggers", command=self.run_triggers).pack(pady=5)
        ctk.CTkButton(frame, text="Export .txt", command=lambda: self.export_text(self.txt_triggers, "trigger_events.txt")).pack()

    def run_triggers(self):
        if not self.trigger_path: return messagebox.showwarning("Warning", "Please select a folder first.")
        self.txt_triggers.delete(1.0, tk.END)
        out = self.find_and_list_trigger_events(self.trigger_path)
        self.txt_triggers.insert(tk.END, out or "No triggers found.")
        messagebox.showinfo("Done", "Triggers scan complete.")

    def build_webhooks_tab(self):
        tab = self.tabview.tab("Webhooks")
        frame = ctk.CTkFrame(tab); frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.txt_webhooks = ctk.CTkTextbox(frame); self.txt_webhooks.pack(fill="both", expand=True)
        ctk.CTkButton(frame, text="Find Webhooks", command=self.run_webhooks).pack(pady=5)
        ctk.CTkButton(frame, text="Delete Webhooks", command=self.run_delete_webhooks).pack(pady=5)
        ctk.CTkButton(frame, text="Export .txt", command=lambda: self.export_text(self.txt_webhooks, "discord_webhooks.txt")).pack()

    def run_webhooks(self):
        if not self.trigger_path: return messagebox.showwarning("Warning", "Please select a folder first.")
        self.txt_webhooks.delete(1.0, tk.END)
        matches = self.find_discord_webhooks(self.trigger_path)
        text = "".join(f"{fp} | {url}\n" for fp, url in matches)
        self.txt_webhooks.insert(tk.END, text or "No webhooks found.")
        messagebox.showinfo("Done", "Webhook scan complete.")

    def run_delete_webhooks(self):
        path = os.path.join(self.output_dir, "discord_webhooks.txt")
        if not os.path.isfile(path): return messagebox.showwarning("Warning", "Run webhook scan and export first.")
        self.load_and_delete_webhooks(path)
        messagebox.showinfo("Done", "Webhook deletion complete.")

    def build_anticheat_tab(self):
        tab = self.tabview.tab("Anticheat")
        frame = ctk.CTkFrame(tab); frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.txt_ac = ctk.CTkTextbox(frame); self.txt_ac.pack(fill="both", expand=True)
        ctk.CTkButton(frame, text="Keyword Scan", command=self.run_ac).pack(pady=5)
        ctk.CTkButton(frame, text="Detect Popular ACs", command=self.run_ac_files).pack(pady=5)
        ctk.CTkButton(frame, text="Export Keywords .txt", command=lambda: self.export_text(self.txt_ac, "anticheat_keywords.txt")).pack()

    def run_ac(self):
        if not self.trigger_path: return messagebox.showwarning("Warning", "Please select a folder first.")
        self.txt_ac.delete(1.0, tk.END)
        out = self.check_for_anticheat_keywords(self.trigger_path)
        self.txt_ac.insert(tk.END, out or "No anticheat keywords found.")
        messagebox.showinfo("Done", "Keyword scan complete.")

    def run_ac_files(self):
        if not self.trigger_path: return messagebox.showwarning("Warning", "Please select a folder first.")
        results = self.check_for_acs_in_path(self.trigger_path)
        msg = "\n".join(results)
        self.txt_ac.delete(1.0, tk.END)
        self.txt_ac.insert(tk.END, msg or "No known AC files found.")
        messagebox.showinfo("Done", "AC file detection complete.")

    def build_variables_tab(self):
        tab = self.tabview.tab("Variables")
        frame = ctk.CTkFrame(tab); frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.txt_vars = ctk.CTkTextbox(frame); self.txt_vars.pack(fill="both", expand=True)
        ctk.CTkButton(frame, text="Find Variables", command=self.run_vars).pack(pady=5)
        ctk.CTkButton(frame, text="Export .txt", command=lambda: self.export_text(self.txt_vars, "variables.txt")).pack()

    def run_vars(self):
        if not self.trigger_path: return messagebox.showwarning("Warning", "Please select a folder first.")
        self.txt_vars.delete(1.0, tk.END)
        out = self.find_and_list_variables(self.trigger_path)
        self.txt_vars.insert(tk.END, out or "No variables found.")
        messagebox.showinfo("Done", "Variable scan complete.")

    def build_builder_tab(self):
        tab = self.tabview.tab("Trigger Builder")
        frame = ctk.CTkFrame(tab); frame.pack(fill="both", expand=True, padx=10, pady=10)
        self.entry_builder = ctk.CTkTextbox(frame, height=250); self.entry_builder.pack(fill="both", expand=True)
        ctk.CTkButton(frame, text="Save Trigger", command=self.save_trigger).pack(pady=5)

    def save_trigger(self):
        code = self.entry_builder.get(1.0, tk.END).strip()
        if not code: return messagebox.showwarning("Empty", "No code to save.")
        save_path = os.path.join(self.output_dir, "built_trigger.lua")
        with open(save_path, "w", encoding="utf-8") as f: f.write(code)
        messagebox.showinfo("Saved", f"Trigger saved to {save_path}")

    def build_settings_tab(self):
        tab = self.tabview.tab("Settings")
        frame = ctk.CTkFrame(tab); frame.pack(fill="both", expand=True, padx=10, pady=10)
        ctk.CTkLabel(frame, text="Settings placeholder").pack(pady=20)

    def export_text(self, widget, filename):
        data = widget.get(1.0, tk.END)
        p = os.path.join(self.output_dir, filename)
        with open(p, "w", encoding="utf-8") as f: f.write(data)

    # ---------- Logic from original ----------
    def find_and_list_trigger_events(self, path):
        events = []
        for root, _, files in os.walk(path):
            for fn in files:
                if fn.endswith('.lua'):
                    fp = os.path.join(root, fn)
                    folder = os.path.basename(root)
                    try:
                        with open(fp, 'r', encoding='latin-1', errors='ignore') as file:
                            for ln, line in enumerate(file, 1):
                                if re.search(r"\b(TriggerServerEvent|TriggerEvent)\b", line):
                                    events.append(f"[{folder}] Line {ln}: {line.strip()}\n")
                    except:
                        continue
        return ''.join(events)

    def find_discord_webhooks(self, path):
        pat = re.compile(r"https://discord\.com/api/webhooks/\w+/\w+")
        found = []
        def proc(fpath):
            try:
                with open(fpath, 'r', encoding='utf-8', errors='ignore') as file:
                    txt = file.read()
                for m in pat.findall(txt):
                    try:
                        if requests.get(m).status_code == 200:
                            found.append((fpath, m))
                    except:
                        pass
            except:
                pass
        for root, _, files in os.walk(path):
            for fn in files:
                proc(os.path.join(root, fn))
        # save to file
        with open(os.path.join(self.output_dir, 'discord_webhooks.txt'), 'w', encoding='utf-8') as o:
            o.write("File | Webhook\n" + "-"*40 + "\n")
            for fpath, url in found: o.write(f"{fpath} | {url}\n")
        return found

    def load_and_delete_webhooks(self, file_path):
        try:
            lines = open(file_path, 'r', encoding='utf-8').read().splitlines()[2:]
            for line in lines:
                parts = line.split('|')
                if len(parts) > 1:
                    try:
                        requests.delete(parts[1].strip())
                    except:
                        pass
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def check_for_anticheat_keywords(self, path):
        results = []
        for root, dirs, files in os.walk(path):
            for ignore in self.folders_to_ignore:
                if ignore in dirs: dirs.remove(ignore)
            for fn in files:
                if fn.endswith('.lua'):
                    fp = os.path.join(root, fn); folder = os.path.basename(root)
                    try:
                        with open(fp, 'r', encoding='latin-1', errors='ignore') as file:
                            for ln, line in enumerate(file, 1):
                                for kw in self.anticheat_keywords:
                                    if kw in line:
                                        results.append(f"[{folder}] Line {ln}: {line.strip()}\n")
                                        break
                    except:
                        continue
        # save file
        with open(os.path.join(self.output_dir, 'anticheat_keywords.txt'), 'w', encoding='utf-8') as o:
            o.writelines(results)
        return results

    def check_for_acs_in_path(self, path):
        detected = []
        for root, dirs, files in os.walk(path):
            for fn in files:
                if fn in self.ac_files_map:
                    folder = os.path.basename(root)
                    detected.append(f"{self.ac_files_map[fn]} AC detected in {folder}\n")
        # save
        with open(os.path.join(self.output_dir, 'acs_founds.txt'), 'w', encoding='utf-8') as o:
            o.writelines(detected)
        return detected

    def find_and_list_variables(self, path):
        vars_list = []
        for root, _, files in os.walk(path):
            for fn in files:
                if fn.endswith('.lua'):
                    fp = os.path.join(root, fn); folder = os.path.basename(root)
                    try:
                        with open(fp, 'r', encoding='latin-1', errors='ignore') as file:
                            for ln, line in enumerate(file, 1):
                                if re.search(r'\bvar_\w+\b', line):
                                    vars_list.append(f"[{folder}] Line {ln}: {line.strip()}\n")
                    except:
                        continue
        with open(os.path.join(self.output_dir, 'variables.txt'), 'w', encoding='utf-8') as o:
            o.writelines(vars_list)
        return vars_list

if __name__ == "__main__":
    app = FemDumperApp()
    app.mainloop()
