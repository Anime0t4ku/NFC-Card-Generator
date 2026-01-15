# NFC Card Generator

**nfc-card-generator.py** is a Python-based GUI application for generating NFC-enabled game cards using predefined visual templates. It allows you to quickly create consistent, print-ready card images with minimal manual adjustment.

The tool is designed around repeatability and ease of use, making it ideal for physical game card projects, retro game collections, and NFC-based launch or display systems.

---

## Features

- Desktop GUI built with Tkinter
- Supports multiple predefined base templates
- Live preview of the generated card
- Automatic artwork scaling while preserving aspect ratio
- Template-aware image placement with fixed clear areas
- SteamGridDB-powered artwork search and selection
- Bundled system logo pack for consistent platform branding
- Configurable output directory
- Automatic saving to the selected output folder
- Optional one-click access to the output folder
- Visual confirmation message when images are saved
- Persistent settings stored in `config.json`

---

## Base Templates

The application currently includes **five base templates**, each with its own layout and visual style.  
Templates are designed with fixed clear areas to ensure correct artwork placement and consistent results.

---

## Included Assets

This repository includes a **system logo pack** containing commonly used platform and console logos.

These logos are intended to be used directly with the included templates and are positioned automatically to match each template’s layout.

---

## Screenshot

![NFC Card Generator Screenshot](templates/screenshot.png)

*Example showing template selection, SteamGridDB artwork search, live preview, and system logo integration.*

---

## Requirements

- Python 3.9 or newer
- Pillow
- Requests
- SteamGridDB API key

---

## SteamGridDB API

Artwork search functionality is powered by the **SteamGridDB API**.

A valid API key is **required** to search for and retrieve game artwork.

### Obtaining an API key

1. Create an account at https://www.steamgriddb.com
2. Open your account settings
3. Generate a personal API key

The API key must be entered into the application when prompted or added to the configuration file.

Without a SteamGridDB API key, artwork search will not function.

---

## Tkinter (Linux Users)

On some Linux distributions, **Tkinter is not installed by default** and must be installed manually.

Required package:

    python3-pillow-tk

If Tkinter is missing, the application will fail to launch.

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

On first launch, the application automatically creates a `config.json` file.

Stored settings include:

- Output directory
- SteamGridDB API key

These settings persist between sessions, allowing the application to start with your previous configuration intact.

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
