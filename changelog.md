# Changelog

All notable changes to **NFC Card Generator** are documented in this file.

The project follows a simple versioning scheme focused on stability and feature milestones rather than strict semantic versioning.

---

## v1.8.3 – Stable Release

### Added
- Unified search workflow for **games, movies, and TV shows**
- TMDB support for official movie and TV posters
- HTTP(S) URL support for:
  - Poster images
  - System logos
- Optional caching of URL-loaded images to a local `web-images` folder
- Keyboard support:
  - Press **Enter** to search
  - Press **Enter** to confirm URL input dialogs
- Automatic poster orientation detection (vertical / horizontal)
- Dynamic crop controls that adapt to image orientation
- Timestamped output filenames to prevent overwrites

### Improved
- Search no longer requires a system logo to be set first
- Clearer empty-state placeholder messaging
- Non-blocking asynchronous image loading
- Cleaner, less crowded UI layout
- More consistent preview scaling behavior
- More robust handling of missing or optional assets (logos)

### Fixed
- UI freezing during image downloads
- Incorrect crop behavior with oversized posters
- Logo overlap issues on Template 3
- Preview resizing edge cases
- Output folder persistence issues

---

## v1.8.2

### Added
- Optional URL image caching setting
- Manual crop slider improvements
- Horizontal poster crop helpers (left / right / manual X)

### Improved
- Better template-specific image positioning
- Improved handling of user-supplied images with non-standard resolutions

### Fixed
- Incorrect clear-area fill on certain templates
- Crop slider not updating correctly in some modes

---

## v1.8.1

### Added
- Poster import directly from local files
- Support for user-supplied artwork without API usage

### Improved
- Preview rendering performance
- Template switching behavior while keeping selected artwork

---

## v1.0 – Major Workflow Update

### Added
- Multi-template rendering system
- Live preview panel
- Persistent output directory
- Automatic save-to-folder workflow
- Status feedback after saving images

### Improved
- Overall application stability
- Code structure and readability

---

## Notes

- Versions **prior to v1.0** were experimental prototypes and are not fully documented.
- Versions **v1.0 through v1.7** evolved rapidly and were not individually documented due to fast iteration and workflow changes.
- From **v1.8.x onward**, changes are tracked more consistently as the project stabilized.
