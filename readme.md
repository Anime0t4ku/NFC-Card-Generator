# NFC Card Generator

**nfc-card-generator.py** is a Python-based GUI application for generating **print-ready NFC card artwork** using predefined visual templates.
It supports **games, movies, and TV shows**, allowing you to browse, preview, and combine artwork sources to create consistent NFC card images with minimal manual adjustment.

The tool is designed around **repeatability, flexibility, and a keyboard-friendly workflow**, making it ideal for physical NFC card projects, retro collections, and media-based launch or display systems.

---

## Nightly builds

### Download the latest builds from continuous integration:

| Name                    | Status                            | File                                        |
|-------------------------|-----------------------------------|---------------------------------------------|
| NFC Card Generator      | [![Build Status][Build]][Actions] | [![Emulator][Download]][NFC Card Generator] |

[Actions]: https://github.com/Anime0t4ku/NFC-Card-Generator/actions/workflows/build.yml
[Build]: https://github.com/Anime0t4ku/NFC-Card-Generator/actions/workflows/build.yml/badge.svg
[Download]: https://img.shields.io/badge/Download-blue
[NFC Card Generator]: https://github.com/Anime0t4ku/NFC-Card-Generator/releases/download/Pre-release/NFC-Card-Generator.zip

---

## Screenshots

![NFC Card Generator Screenshot](NFC-Card-Generator/templates/screenshot.png)

*Example showing game artwork.*

![NFC Card Generator Screenshot 2](NFC-Card-Generator/templates/screenshot2.png)

*Example showing movie and TV artwork.*

---

## Features

### General
- Desktop GUI built with Tkinter
- Live preview of the generated card
- Automatic artwork scaling while preserving aspect ratio
- Template-aware image placement using fixed clear areas
- Manual crop adjustment when needed
- Keyboard-friendly workflow (Enter to search, Enter to load URLs)
- Persistent settings stored in `config.json`

---

### Game Artwork (SteamGridDB)
- Search and select games via SteamGridDB
- Multiple community-created posters per game
- Vertical poster filtering for card-friendly layouts
- Asynchronous image loading with no UI freezing

---

### Movie & TV Artwork (TMDB)
- Unified search for movies and TV shows
- Official posters retrieved directly from TMDB
- Displays all available poster variants per title
- English posters preferred with automatic fallback
- Automatic release year detection for accurate naming

---

### Unified Search Workflow
- Single search bar for all content types
- Source selector for SteamGridDB or TMDB
- Title picker dialog for search results
- Shared thumbnail grid for all artwork sources
- Posters can be browsed without selecting a system logo first

---

### Templates & Rendering
- Supports multiple predefined base templates
- Framed and layered layout styles
- Header and footer logo placement (optional)
- Automatic logo scaling and alignment per template
- Template previews shown directly in the UI

---

### System Logos
- Import system logos from disk
- Load system logos directly from HTTP(S) URLs
- Optional logo usage, cards can be generated without a logo
- Logos are automatically resized and positioned per template

---

### Poster Image Support
- Import custom poster images from disk
- Load poster images directly from HTTP(S) URLs
- Automatic orientation detection (horizontal / vertical)
- Crop controls adapt based on image orientation
- Works without any API usage
- Suitable for fan art or custom designs

---

### Output & File Handling
- Configurable output directory
- Automatic saving to the selected output folder
- One-click access to the output folder
- Timestamped filenames to prevent overwrites
- Movie and TV titles include release year in filenames
- Optional caching of URL-loaded images to disk

---

### API Key Management
- SteamGridDB and TMDB API keys stored locally
- Keys requested only when required
- Separate handling per service
- No hardcoded credentials

---

## Base Templates

The application currently includes **five base templates**, each with its own layout and visual style.
Templates are designed with fixed clear areas to ensure correct artwork placement and consistent results.

---

## Included Assets

This repository includes a **system logo pack** containing commonly used platform and console logos.

These logos are intended to be used directly with the included templates and are positioned automatically to match each template’s layout.

---

## Requirements

- Python 3.9 or newer
- Pillow
- Requests
- SteamGridDB API key (for game artwork)
- TMDB API key (for movie and TV artwork)

---

## API Keys

### SteamGridDB
Used for searching and retrieving game artwork.

1. Create an account at https://www.steamgriddb.com
2. Open your account settings
3. Generate a personal API key

---

### TMDB (The Movie Database)
Used for searching and retrieving movie and TV posters.

1. Create an account at https://www.themoviedb.org
2. Go to Settings → API
3. Generate an API key

API keys are requested by the application when needed and stored locally.

---

## Tkinter (Linux Users)

On some Linux distributions, **Tkinter is not installed by default** and must be installed manually.

Required package: `python3-pillow-tk`

If Tkinter is missing, the application will fail to launch.

---

## Installation

Clone the repository:

git clone https://github.com/yourusername/nfc-card-generator.git
cd nfc-card-generator

Install dependencies:

pip install -r requirements.txt

Run the application:

python nfc-card-generator.py

---

## Configuration

On first launch, the application automatically creates a `config.json` file.

Stored settings include:
- Output directory
- SteamGridDB API key
- TMDB API key
- URL image caching preference

All settings persist between sessions.

---

## Output Folder Behavior

- When an output folder is set, generated images are saved automatically
- No save dialog is shown during normal operation
- A confirmation message appears after saving and disappears after a few seconds
- An **Open Output Folder** button becomes available once a folder is configured

---

## Notes

- Images always maintain their original aspect ratio
- Template clear areas are respected to avoid unwanted cropping
- Logos are optional and template-aware
- The project is intended for personal and hobbyist use

---

## License

This project is released under the MIT License.
You are free to modify, distribute, and use it for personal or commercial projects.
