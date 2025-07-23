# FemDumper

FemDumper is a Python tool for analysing FiveM server dumps.  It comes with a
graphical user interface written with **PyQt6**.

## 🚀 Installation

1. Ensure Python 3.10 or newer is installed.
2. Install the required packages (exact versions are pinned in
   `requirements.txt`):

```bash
pip install -r requirements.txt
```

## 📦 Usage

Launch the GUI with:

```bash
python GUI/femdumpergui.py
```

The application stores its output under a folder named `FemDumper` on your
desktop.

## ✨ Features
- **Trigger Scanner** – finds `TriggerServerEvent` and `TriggerEvent` calls.
- **Webhook Scanner** – locates valid Discord webhooks.
- **Anti‑Cheat Detection** – scans for known anti‑cheat systems and keywords.
- **Variable Scanner** – identifies special variables.
- **Item Viewer** – displays item images found in the dump.
- **Trigger Builder** – generates sample code for FiveM triggers.
