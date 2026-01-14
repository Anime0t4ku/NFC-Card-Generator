# NFC Card Generator

**nfc-card-generator.py** is a Python-based GUI tool designed to generate NFC-enabled game cards using predefined visual templates. It allows you to quickly create consistent, print-ready images while embedding NFC metadata into your workflow.

The application is built with simplicity and repeatability in mind, making it ideal for physical game card projects, retro collections, and NFC-based launch systems.

---

## Features

- Graphical user interface built with Tkinter
- Supports multiple base templates
- Automatic image placement while preserving aspect ratio
- Configurable output directory
- Persistent settings stored in `config.json`
- One-click access to the output folder
- Visual feedback when images are successfully saved
- Includes a bundled system logo pack for use with the templates

---

## Base Templates

The application currently includes **three base templates**.

---

## Included Assets

This repository includes a **system logo pack** containing commonly used platform and console logos.  
These logos are intended to be used directly with the provided templates and help ensure consistent visual results.

---

## Screenshot

![NFC Card Generator Screenshot](templates/screenshot.png)

*Example showing template selection, artwork search, live preview, and system logo integration.*

---

## Requirements

- Python 3.9 or newer
- Pillow
- Requests

---

## Tkinter (Linux users)

On Linux systems, **Tkinter is not always installed by default** and must be installed manually.

Required package:

    python3-pillow-tk

If Tkinter is missing, the application will not start.

---

## Installation

### Clone the repository

    git clone https://github.com/yourusername/nfc-card-generator.git
    cd nfc-card-generator

### Install dependencies

    pip install pillow requests

### Run the application

    python nfc-card-generator.py

---

## Configuration

The application automatically creates a `config.json` file on first run.

Stored settings include:

- Selected output directory

This allows the app to remember your preferences between sessions without requiring reconfiguration.

---

## Output Folder Behavior

- When an output folder is set, generated images are saved automatically
- No save dialog is shown during normal operation
- A confirmation message appears after saving and disappears after a few seconds
- A **Go to output folder** button becomes available once a folder is configured

---

## Notes

- Images always maintain their original aspect ratio
- Template clear areas are respected to avoid unwanted cropping
- The project is intended for personal and hobbyist use

---

## License

This project is released under the MIT License.  
You are free to modify, distribute, and use it for personal or commercial projects.
