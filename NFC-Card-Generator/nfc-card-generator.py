import requests
from PIL import Image, ImageTk, ImageDraw
from io import BytesIO
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
import threading
import sys
import subprocess
import re
import webbrowser
from datetime import datetime

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

# ---------------- CONFIG ----------------

CONFIG_FILE = "config.json"

CLEAR_W = 609
CLEAR_H = 840

T3_MAX_HEIGHT = 840
T3_OVERFLOW_PAD = 120

T4_POSTER_W = 619
T4_POSTER_H = 834
T4_POSTER_Y = 80

TEMPLATES = {
    "Black with Pins": {
        "image_path": "templates/template_1.png",
        "center": {
            "x": 10,
            "y": 59,
            "w": 597,
            "h": 855
        },
        "footer": {
            "height": 90,
            "logo_height": 46,
            "max_width": 300,
            "logo_margin": 25
        },
        "mode": "framed"
    },

    "White with Pins": {
        "image_path": "templates/template_2.png",
        "center": {
            "x": 14,
            "y": 63,
            "w": 591,
            "h": 849
        },
        "footer": {
            "height": 90,
            "logo_height": 46,
            "max_width": 300,
            "logo_margin": 25
        },
        "mode": "framed"
    },

    "HuCard Style": {
        "image_path": "templates/template_3.png",
        "poster_y": 150,  # Perfect starting point
        "header_logo": {
            "height": 63,
            "max_width": 250,
            "top_margin": 62,
            "left_margin": 24
        },
        "mode": "layered"
    },

    "Black": {
        "image_path": "templates/template_4.png",
        "header_logo": {
            "max_height": 62,
            "max_width": 300,
            "top_margin": 10
        },
        "mode": "framed-top-logo"
    },

    "White": {
        "image_path": "templates/template_5.png",
        "header_logo": {
            "max_height": 62,
            "max_width": 300,
            "top_margin": 10
        },
        "mode": "framed-top-logo"
    },

    "Poster Only": {
        "image_path": "templates/template_6.png",
        "size": {
            "w": 619,
            "h": 994
        },
        "corner_radius": 22,
        "mode": "full-poster-rounded"
    }
}


THUMB_W = 160
THUMB_H = 240
ICON_THUMB_SIZE = 160
ICON_PADDING = 16
THUMBS_PER_ROW = 3
TEMPLATE_THUMB_W = 140

PREVIEW_MIN_W = 340
PREVIEW_MIN_H = 520

API_KEY = None        # SteamGridDB
TMDB_API_KEY = None   # TMDB
TMDB_IMG_BASE = "https://image.tmdb.org/t/p/original"
WEB_IMAGE_DIR = "web-images"
WEB_POSTER_DIR = os.path.join(WEB_IMAGE_DIR, "posters")
WEB_LOGO_DIR = os.path.join(WEB_IMAGE_DIR, "logos")



# ---------------- CONFIG HELPERS ----------------

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def load_api_key(service="steamgriddb"):
    cfg = load_config()
    return cfg.get(f"{service}_api_key")

def save_api_key(key, service="steamgriddb"):
    cfg = load_config()
    cfg[f"{service}_api_key"] = key
    save_config(cfg)

def load_output_dir():
    return load_config().get("output_directory")

def save_output_dir(path):
    cfg = load_config()
    cfg["output_directory"] = path
    save_config(cfg)

def load_cache_posters():
    return load_config().get("cache_web_posters", False)

def save_cache_posters(value: bool):
    cfg = load_config()
    cfg["cache_web_posters"] = value
    save_config(cfg)

def load_cache_logos():
    return load_config().get("cache_web_logos", False)

def save_cache_logos(value: bool):
    cfg = load_config()
    cfg["cache_web_logos"] = value
    save_config(cfg)

def load_search_cached_logos():
    return load_config().get("search_cached_web_logos", False)

def save_search_cached_logos(value: bool):
    cfg = load_config()
    cfg["search_cached_web_logos"] = value
    save_config(cfg)

def load_icon_pack_dir():
    return load_config().get("icon_pack_directory")

def save_icon_pack_dir(path):
    cfg = load_config()
    cfg["icon_pack_directory"] = path
    save_config(cfg)

def headers():
    return {"Authorization": f"Bearer {API_KEY}"}

def sanitize_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    return re.sub(r"\s+", " ", name).strip()

# ---------------- STEAMGRIDDB ----------------

def search_games(name):
    r = requests.get(
        f"https://www.steamgriddb.com/api/v2/search/autocomplete/{name}",
        headers=headers()
    )
    r.raise_for_status()
    return r.json()["data"]

def get_grids(game_id):
    r = requests.get(
        f"https://www.steamgriddb.com/api/v2/grids/game/{game_id}",
        headers=headers()
    )
    r.raise_for_status()
    return r.json()["data"]


# ---------------- TMDB ----------------

def tmdb_search_multi(query):
    r = requests.get(
        "https://api.themoviedb.org/3/search/multi",
        params={
            "api_key": load_api_key("tmdb"),
            "query": query,
            "include_adult": False
        },
        timeout=10
    )
    r.raise_for_status()

    results = []
    for item in r.json().get("results", []):
        if item.get("media_type") not in ("movie", "tv"):
            continue

        title = item.get("title") or item.get("name")
        year = None

        if item.get("release_date"):
            year = item["release_date"][:4]
        elif item.get("first_air_date"):
            year = item["first_air_date"][:4]

        results.append({
            "id": item["id"],
            "title": title,
            "year": year,
            "media_type": item["media_type"]
        })

    return results


def tmdb_get_posters(item):
    media_type = item["media_type"]
    tmdb_id = item["id"]

    r = requests.get(
        f"https://api.themoviedb.org/3/{media_type}/{tmdb_id}/images",
        params={
            "api_key": load_api_key("tmdb"),
            "include_image_language": "en,null"
        },
        timeout=10
    )
    r.raise_for_status()

    return r.json().get("posters", [])

def search_system_icons(query, root):
    results = []
    q = query.lower()

    for base, _, files in os.walk(root):
        for f in files:
            if not f.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
                continue
            if q in f.lower():
                results.append(os.path.join(base, f))

    return results


# ---------------- IMAGE HELPERS ----------------

def fit_inside(img, max_w, max_h):
    scale = min(max_w / img.width, max_h / img.height)
    new_w = int(img.width * scale)
    new_h = int(img.height * scale)

    resized = img.resize((new_w, new_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (max_w, max_h), (0, 0, 0, 0))
    x = (max_w - new_w) // 2
    y = (max_h - new_h) // 2
    canvas.paste(resized, (x, y), resized)

    return canvas

def maybe_cache_web_image(img, url, kind="poster"):
    if kind == "poster" and not load_cache_posters():
        return img
    if kind == "logo" and not load_cache_logos():
        return img

    base_dir = WEB_LOGO_DIR if kind == "logo" else WEB_POSTER_DIR
    os.makedirs(base_dir, exist_ok=True)

    # Always normalize cached web images to PNG
    name = os.path.basename(url.split("?")[0])
    name = os.path.splitext(name)[0] + ".png"

    path = os.path.join(base_dir, name)

    try:
        img = img.convert("RGBA")
        img.save(path, format="PNG")  # explicit format fixes JPG/WebP issues
        print(f"Cached web image → {path}")
    except Exception as e:
        print("Failed to cache web image:", e)

    return img

def load_image_from_url(url, timeout=10):
    if not url.lower().startswith(("http://", "https://")):
        raise ValueError("Only http(s) URLs are supported")

    r = requests.get(url, timeout=timeout)
    r.raise_for_status()

    return Image.open(BytesIO(r.content)).convert("RGBA")

def cover_image(img, w, h):
    ratio = max(w / img.width, h / img.height)
    r = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    x = (r.width - w) // 2
    y = (r.height - h) // 2
    return r.crop((x, y, x + w, y + h))

def cover_image_top(img, w, h):
    ratio = max(w / img.width, h / img.height)
    r = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    x = (r.width - w) // 2
    return r.crop((x, 0, x + w, h))

def cover_image_bottom(img, w, h):
    ratio = max(w / img.width, h / img.height)
    r = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    x = (r.width - w) // 2
    y = r.height - h
    return r.crop((x, y, x + w, y + h))

def cover_image_manual(img, w, h, offset):
    ratio = max(w / img.width, h / img.height)
    r = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)

    x = (r.width - w) // 2
    max_y = r.height - h

    # Map slider (0–1000) to actual vertical range (0–max_y)
    if max_y > 0:
        y = int((offset / 1000) * max_y)
    else:
        y = 0

    return r.crop((x, y, x + w, y + h))


def apply_rounded_corners(img, radius):
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)

    draw.rounded_rectangle(
        (0, 0, img.width, img.height),
        radius=radius,
        fill=255
    )

    out = Image.new("RGBA", img.size)
    out.paste(img, (0, 0), mask)
    return out

def apply_rounded_mask(img, radius):
    mask = Image.new("L", img.size, 0)
    draw = ImageDraw.Draw(mask)

    draw.rounded_rectangle(
        (2, 2, img.width - 2, img.height - 2),
        radius=radius - 2,
        fill=255
    )

    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out

# --- HORIZONTAL HELPERS ---

def cover_image_left(img, w, h):
    ratio = max(w / img.width, h / img.height)
    r = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    y = (r.height - h) // 2
    return r.crop((0, y, w, y + h))

def cover_image_right(img, w, h):
    ratio = max(w / img.width, h / img.height)
    r = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    y = (r.height - h) // 2
    x = r.width - w
    return r.crop((x, y, x + w, y + h))

def cover_image_manual_x(img, w, h, offset):
    ratio = max(w / img.width, h / img.height)
    r = img.resize((int(img.width * ratio), int(img.height * ratio)), Image.LANCZOS)
    y = (r.height - h) // 2
    max_x = r.width - w
    x = max(0, min(max_x, int(offset)))
    return r.crop((x, y, x + w, y + h))

def fit_to_width(img, target_width):
    scale = target_width / img.width
    return img.resize((target_width, int(img.height * scale)), Image.LANCZOS)

def force_vertical_overflow(img, min_height):
    if img.height >= min_height:
        return img
    scale = min_height / img.height
    return img.resize(
        (int(img.width * scale), int(img.height * scale)),
        Image.LANCZOS
    )

def apply_footer_logo(base, logo, cfg):
    if isinstance(logo, str):
        logo = Image.open(logo).convert("RGBA")

    f = cfg["footer"]

    # Scale by height first
    scale = f["logo_height"] / logo.height
    new_w = int(logo.width * scale)
    new_h = f["logo_height"]

    logo = logo.resize((new_w, new_h), Image.LANCZOS)

    # Enforce max width if defined
    if "max_width" in f and logo.width > f["max_width"]:
        scale = f["max_width"] / logo.width
        logo = logo.resize(
            (f["max_width"], int(logo.height * scale)),
            Image.LANCZOS
        )

    y = base.height - f["height"] + (f["height"] - logo.height) // 2
    base.paste(logo, (f["logo_margin"], y), logo)


def apply_header_logo(base, logo, cfg):
    if isinstance(logo, str):
        logo = Image.open(logo).convert("RGBA")

    h = cfg["header_logo"]

    # --- Resize by height first ---
    scale = h["height"] / logo.height
    logo = logo.resize(
        (int(logo.width * scale), h["height"]),
        Image.LANCZOS
    )

    # --- Enforce max width if needed ---
    if logo.width > h["max_width"]:
        scale = h["max_width"] / logo.width
        logo = logo.resize(
            (h["max_width"], int(logo.height * scale)),
            Image.LANCZOS
        )

    # --- LEFT aligned (fixed) ---
    x = h["left_margin"]

    # --- VERTICALLY CENTERED inside header height ---
    header_h = h["height"]
    y = h["top_margin"] + (header_h - logo.height) // 2

    base.paste(logo, (x, y), logo)

def apply_top_center_logo(base, logo, cfg):
    if isinstance(logo, str):
        logo = Image.open(logo).convert("RGBA")

    h = cfg["header_logo"]

    # Scale by height first
    if logo.height > h["max_height"]:
        scale = h["max_height"] / logo.height
        logo = logo.resize(
            (int(logo.width * scale), h["max_height"]),
            Image.LANCZOS
        )

    # Apply max width if present
    if "max_width" in h and logo.width > h["max_width"]:
        scale = h["max_width"] / logo.width
        logo = logo.resize(
            (h["max_width"], int(logo.height * scale)),
            Image.LANCZOS
        )

    # Horizontal center
    x = (base.width - logo.width) // 2

    # Vertical center INSIDE header band
    header_height = h["max_height"]
    y = h["top_margin"] + (header_height - logo.height) // 2

    base.paste(logo, (x, y), logo)

# ---------------- GUI ----------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()

        # --- Window icon ---
        icon_path = resource_path("Icon.png")
        if os.path.exists(icon_path):
            self._window_icon = tk.PhotoImage(file=icon_path)
            self.iconphoto(True, self._window_icon)

        self.title("NFC Card Generator v2.1.2 by Anime0t4ku")
        self.geometry("1200x900")
        self.minsize(1000, 700)


        self.logo_path = None
        self.logo_image = None
        self.cache_web_posters = tk.BooleanVar(value=load_cache_posters())
        self.cache_web_logos = tk.BooleanVar(value=load_cache_logos())
        self.search_cached_logos = tk.BooleanVar(
            value=load_search_cached_logos()
        )

        self.output_image = None
        self.output_dir = load_output_dir()
        self.icon_pack_dir = load_icon_pack_dir()

        self.template_var = tk.StringVar(value="Black with Pins")
        self.crop_mode = tk.StringVar(value="center")
        self.crop_offset = tk.IntVar(value=0)
        self.source_var = tk.StringVar(value="steam")  # steam | tmdb

        self.selected_poster_image = None
        self.poster_orientation = "vertical"
        self.current_game_title = None

        self.template_imgs = {}
        self.thumb_imgs = []
        self.preview_image = None
        self.status_after_id = None
        self.search_id = 0

        self.build_ui()
        self.update_output_folder_button()


    def ensure_api_key(self, service="steamgriddb"):
        global API_KEY, TMDB_API_KEY

        key_var = API_KEY if service == "steamgriddb" else TMDB_API_KEY
        if key_var:
            return True

        key = load_api_key(service)
        if key:
            if service == "steamgriddb":
                API_KEY = key
            else:
                TMDB_API_KEY = key
            return True

        title = "SteamGridDB API Key" if service == "steamgriddb" else "TMDB API Key"

        if service == "steamgriddb":
            info_text = (
                "You need a free SteamGridDB account to use the API.\n\n"
                "Create an account and generate an API key here:"
            )
            api_url = "https://www.steamgriddb.com/profile/preferences/api"
        else:
            info_text = (
                "You need a free TMDB account to use the API.\n\n"
                "Create an account and request an API key here:"
            )
            api_url = "https://www.themoviedb.org/settings/api"

        d = tk.Toplevel(self)
        d.title(title)
        d.geometry("520x260")
        d.transient(self)
        d.grab_set()

        ttk.Label(
            d,
            text=info_text,
            wraplength=480,
            justify="left"
        ).pack(pady=(10, 6), padx=10)

        link = ttk.Label(
            d,
            text=api_url,
            foreground="blue",
            cursor="hand2",
            wraplength=480
        )
        link.pack(pady=(0, 12))
        link.bind("<Button-1>", lambda e, url=api_url: webbrowser.open(url))

        ttk.Label(d, text=f"Enter your {title}:").pack()

        key_var = tk.StringVar()
        e = ttk.Entry(d, textvariable=key_var, width=60)
        e.pack(pady=6, padx=10)
        e.focus()

        def save_and_close(event=None):
            key = key_var.get().strip()
            if key:
                save_api_key(key, service)
            d.destroy()

        e.bind("<Return>", save_and_close)

        ttk.Button(
            d,
            text="Save",
            command=save_and_close
        ).pack(pady=10)

        d.wait_window()

        key = load_api_key(service)
        if service == "steamgriddb":
            API_KEY = key
        else:
            TMDB_API_KEY = key

        return key is not None

    def build_source_controls(self, refresh=False):
        if refresh and hasattr(self, "source_frame"):
            self.source_frame.destroy()

        self.source_frame = ttk.Frame(self.source_container)
        self.source_frame.pack(side="left", padx=(6, 0))

        ttk.Label(self.source_frame, text="Source:").pack(side="left", padx=(0, 4))

        ttk.Radiobutton(
            self.source_frame,
            text="SteamGridDB",
            variable=self.source_var,
            value="steam"
        ).pack(side="left")

        ttk.Radiobutton(
            self.source_frame,
            text="TMDB",
            variable=self.source_var,
            value="tmdb"
        ).pack(side="left")

        logo_search_enabled = (
                (self.icon_pack_dir and os.path.isdir(self.icon_pack_dir)) or
                self.search_cached_logos.get()
        )

        if logo_search_enabled:
            ttk.Radiobutton(
                self.source_frame,
                text="System Logos",
                variable=self.source_var,
                value="system"
            ).pack(side="left")

    def choose_icon_pack_dir(self):
        path = filedialog.askdirectory()
        if not path:
            return

        self.icon_pack_dir = path
        save_icon_pack_dir(path)

        self.icon_pack_btn.config(text="Change System Icon Pack Folder")

        self.build_source_controls(refresh=True)
        self.show_status("System icon pack folder set")

    def _on_mousewheel(self, event):
        if sys.platform.startswith("win"):
            self.canvas.yview_scroll(-1 * int(event.delta / 120), "units")
        elif sys.platform == "darwin":
            self.canvas.yview_scroll(-1 * int(event.delta), "units")
        else:
            if event.num == 4:
                self.canvas.yview_scroll(-1, "units")
            elif event.num == 5:
                self.canvas.yview_scroll(1, "units")

    # -------- UI BUILD --------

    def build_template_selector(self):
        frame = ttk.LabelFrame(self, text="Select Template")
        frame.pack(pady=10)

        for name, cfg in TEMPLATES.items():
            img = Image.open(resource_path(cfg["image_path"]))
            img = img.resize(
                (TEMPLATE_THUMB_W, int(TEMPLATE_THUMB_W * img.height / img.width)),
                Image.LANCZOS
            )
            tk_img = ImageTk.PhotoImage(img)
            self.template_imgs[name] = tk_img

            ttk.Radiobutton(
                frame,
                image=tk_img,
                text=name,
                compound="top",
                value=name,
                variable=self.template_var,
                command=self.render_with_current_template
            ).pack(side="left", padx=8)

    def build_crop_controls(self):
        frame = ttk.LabelFrame(self, text="Poster Crop Mode")
        frame.pack(pady=6)

        self.crop_buttons = {}

        for m in ("center", "top", "bottom", "manual"):
            btn = ttk.Radiobutton(
                frame,
                text=m.capitalize(),
                value=m,
                variable=self.crop_mode,
                command=self.render_with_current_template
            )
            btn.pack(side="left", padx=6)
            self.crop_buttons[m] = btn

        self.crop_slider = ttk.Scale(
            frame,
            from_=0,
            to=1000,
            orient="horizontal",
            variable=self.crop_offset,
            command=lambda e: self.render_with_current_template()
        )

    def update_crop_labels(self):
        if not hasattr(self, "crop_buttons"):
            return

        if self.poster_orientation == "horizontal":
            self.crop_buttons["top"].config(text="Left")
            self.crop_buttons["bottom"].config(text="Right")
        else:
            self.crop_buttons["top"].config(text="Top")
            self.crop_buttons["bottom"].config(text="Bottom")

    def build_ui(self):
        self.build_template_selector()
        self.build_crop_controls()

        controls_outer = ttk.Frame(self)
        controls_outer.pack(pady=5, fill="x")

        controls = ttk.Frame(controls_outer)
        controls.pack(anchor="center")

        self.controls = controls

        # LEFT: menus
        self.menu_frame = ttk.Frame(controls)
        self.menu_frame.pack(side="left")

        # MIDDLE: source selector
        self.source_container = ttk.Frame(controls)
        self.source_container.pack(side="left", padx=(10, 10))

        # RIGHT: search + cache
        self.search_container = ttk.Frame(controls)
        self.search_container.pack(side="left")

        self.build_source_controls()

        # --- System Logo menu ---
        logo_menu = tk.Menu(self, tearoff=0)
        logo_menu.add_command(label="Import from file", command=self.load_logo)
        logo_menu.add_command(label="Import from URL", command=self.load_logo_from_url)

        logo_btn = ttk.Menubutton(
            controls,
            text="System Logo",
            menu=logo_menu
        )
        logo_btn.pack(in_=self.menu_frame, side="left", padx=5)

        # --- Poster Image menu ---
        poster_menu = tk.Menu(self, tearoff=0)
        poster_menu.add_command(label="Import from file", command=self.load_local_poster)
        poster_menu.add_command(label="Import from URL", command=self.load_poster_from_url)

        poster_btn = ttk.Menubutton(
            controls,
            text="Poster",
            menu=poster_menu
        )
        poster_btn.pack(in_=self.menu_frame, side="left", padx=5)

        ttk.Label(self.search_container, text="Search:").pack(side="left")

        self.game_entry = ttk.Entry(self.search_container, width=30)
        self.game_entry.pack(side="left", padx=5)

        # Press Enter to search
        self.game_entry.bind("<Return>", lambda e: self.search())

        ttk.Button(
            self.search_container,
            text="Search",
            command=self.search
        ).pack(side="left", padx=(0, 8))

        ttk.Separator(
            self.source_container,
            orient="vertical"
        ).pack(side="right", fill="y", padx=8)

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True)

        main.columnconfigure(1, weight=1)
        main.columnconfigure(2, weight=2)
        main.rowconfigure(0, weight=1)

        selector_container = ttk.Frame(main)
        selector_container.grid(row=0, column=1, padx=20, sticky="n")

        self.canvas = tk.Canvas(selector_container, width=520, height=750)
        self.canvas.pack(side="left")

        sb = ttk.Scrollbar(selector_container, orient="vertical", command=self.canvas.yview)
        sb.pack(side="left", fill="y")
        self.canvas.configure(yscrollcommand=sb.set)
        # Global mouse wheel scrolling for thumbnail canvas
        if sys.platform.startswith("linux"):
            self.bind_all("<Button-4>", self._on_mousewheel)
            self.bind_all("<Button-5>", self._on_mousewheel)
        else:
            self.bind_all("<MouseWheel>", self._on_mousewheel)

        self.thumb_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((260, 0), window=self.thumb_frame, anchor="n")

        self.thumb_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.loading_label = ttk.Label(
            self.thumb_frame,
            text="Loading images…",
            foreground="gray"
        )

        self.placeholder_label = ttk.Label(
            self.thumb_frame,
            text="Search for a game, movie or TV show to load posters\nor use “Poster ▼” to add your own image",
            foreground="gray",
            justify="center"
        )

        self.placeholder_label.grid(
            row=0,
            column=0,
            columnspan=THUMBS_PER_ROW,
            pady=30
        )

        preview = ttk.Frame(main)
        preview.grid(row=0, column=2, padx=40, sticky="nsew")

        ttk.Label(preview, text="Preview").pack(anchor="n")

        preview_frame = ttk.Frame(preview, width=PREVIEW_MIN_W, height=PREVIEW_MIN_H)
        preview_frame.pack(expand=True)
        preview_frame.pack_propagate(False)

        self.preview_label = ttk.Label(preview_frame)
        self.preview_label.pack(expand=True, fill="both")

        bottom = ttk.Frame(main)
        bottom.grid(row=1, column=0, columnspan=3, pady=10)

        ttk.Button(
            bottom,
            text="Settings",
            command=self.open_settings
        ).pack(side="left", padx=10)

        ttk.Button(
            bottom,
            text="Save Image",
            command=self.save
        ).pack(side="left", padx=(10, 5))

        ttk.Button(
            bottom,
            text="Save As…",
            command=self.save_as
        ).pack(side="left", padx=(0, 10))

        self.open_folder_btn = ttk.Button(
            bottom,
            text="Open Output Folder",
            command=self.open_output_dir
        )

        self.status_label = ttk.Label(bottom, text="", foreground="green")
        self.status_label.pack(side="left", padx=15)

    # -------- Settings Menu --------

    def open_settings(self):
        d = tk.Toplevel(self)
        d.title("Settings")
        d.geometry("520x700")
        d.transient(self)
        d.grab_set()

        container = ttk.Frame(d, padding=15)
        container.pack(fill="both", expand=True)

        # ================= TITLE =================
        ttk.Label(
            container,
            text="Settings",
            font=("TkDefaultFont", 11, "bold")
        ).pack(anchor="w")

        # ================= OUTPUT FOLDER =================
        ttk.Label(
            container,
            text="Output Folder",
            font=("TkDefaultFont", 10, "bold")
        ).pack(anchor="w", pady=(15, 4))

        output_dir_var = tk.StringVar(
            value=self.output_dir or "No output folder set"
        )

        ttk.Label(
            container,
            textvariable=output_dir_var,
            foreground="gray",
            wraplength=480
        ).pack(anchor="w", pady=(0, 6))

        def set_output_dir_from_settings():
            path = filedialog.askdirectory(parent=d)
            if not path:
                return

            self.output_dir = path
            save_output_dir(path)
            output_dir_var.set(path)

            self.update_output_folder_button()
            self.show_status("Output folder set")

        ttk.Button(
            container,
            text="Set / Change Output Folder",
            command=set_output_dir_from_settings
        ).pack(anchor="w")

        ttk.Separator(container).pack(fill="x", pady=15)

        # ================= SYSTEM LOGO PACK FOLDER =================
        ttk.Label(
            container,
            text="System Logo Pack Folder",
            font=("TkDefaultFont", 10, "bold")
        ).pack(anchor="w", pady=(10, 4))

        icon_pack_var = tk.StringVar(
            value=self.icon_pack_dir or "No system logo pack folder set"
        )

        ttk.Label(
            container,
            textvariable=icon_pack_var,
            foreground="gray",
            wraplength=480
        ).pack(anchor="w", pady=(0, 6))

        def set_icon_pack_from_settings():
            path = filedialog.askdirectory(parent=d)
            if not path:
                return

            self.icon_pack_dir = path
            save_icon_pack_dir(path)
            icon_pack_var.set(path)
            self.build_source_controls(refresh=True)
            self.show_status("System logo pack folder set")

        ttk.Button(
            container,
            text="Set / Change System Logo Pack Folder",
            command=set_icon_pack_from_settings
        ).pack(anchor="w")

        ttk.Separator(container).pack(fill="x", pady=15)

        # ================= CACHE URL IMAGES =================
        ttk.Label(
            container,
            text="Web Images",
            font=("TkDefaultFont", 10, "bold")
        ).pack(anchor="w", pady=(10, 4))

        ttk.Checkbutton(
            container,
            text="Cache poster images from URLs",
            variable=self.cache_web_posters,
            command=lambda: save_cache_posters(self.cache_web_posters.get())
        ).pack(anchor="w")

        ttk.Checkbutton(
            container,
            text="Cache system logo images from URLs",
            variable=self.cache_web_logos,
            command=lambda: save_cache_logos(self.cache_web_logos.get())
        ).pack(anchor="w")

        def toggle_cached_logo_search():
            save_search_cached_logos(self.search_cached_logos.get())
            self.build_source_controls(refresh=True)

        ttk.Checkbutton(
            container,
            text="Include cached web logos in logo search",
            variable=self.search_cached_logos,
            command=toggle_cached_logo_search
        ).pack(anchor="w")

        ttk.Separator(container).pack(fill="x", pady=15)

        # ================= STEAMGRIDDB API KEY =================
        ttk.Label(
            container,
            text="SteamGridDB API Key",
            font=("TkDefaultFont", 10, "bold")
        ).pack(anchor="w", pady=(10, 4))

        steam_key_var = tk.StringVar(
            value="Set" if load_api_key("steamgriddb") else "Not set"
        )

        ttk.Label(
            container,
            textvariable=steam_key_var,
            foreground="gray"
        ).pack(anchor="w", pady=(0, 6))

        def set_steam_key():
            # Clear current key so ensure_api_key shows the dialog
            save_api_key(None, "steamgriddb")

            global API_KEY
            API_KEY = None

            if self.ensure_api_key("steamgriddb"):
                steam_key_var.set("Set")
                self.show_status("SteamGridDB API key saved")

        def remove_steam_key():
            save_api_key(None, "steamgriddb")
            steam_key_var.set("Not set")

            global API_KEY
            API_KEY = None

            self.show_status("SteamGridDB API key removed")

        btn_row = ttk.Frame(container)
        btn_row.pack(anchor="w")

        ttk.Button(
            btn_row,
            text="Set / Change",
            command=set_steam_key
        ).pack(side="left")

        ttk.Button(
            btn_row,
            text="Remove",
            command=remove_steam_key
        ).pack(side="left", padx=(8, 0))

        ttk.Separator(container).pack(fill="x", pady=18)

        ttk.Button(
            d,
            text="Close",
            command=d.destroy
        ).pack(pady=10)
        # ================= TMDB API KEY =================
        ttk.Label(
            container,
            text="TMDB API Key",
            font=("TkDefaultFont", 10, "bold")
        ).pack(anchor="w", pady=(10, 4))

        tmdb_key_var = tk.StringVar(
            value="Set" if load_api_key("tmdb") else "Not set"
        )

        ttk.Label(
            container,
            textvariable=tmdb_key_var,
            foreground="gray"
        ).pack(anchor="w", pady=(0, 6))

        def set_tmdb_key():
            # Clear current key so ensure_api_key shows the dialog
            save_api_key(None, "tmdb")

            global TMDB_API_KEY
            TMDB_API_KEY = None

            if self.ensure_api_key("tmdb"):
                tmdb_key_var.set("Set")
                self.show_status("TMDB API key saved")

        def remove_tmdb_key():
            save_api_key(None, "tmdb")
            tmdb_key_var.set("Not set")

            global TMDB_API_KEY
            TMDB_API_KEY = None

            self.show_status("TMDB API key removed")

        btn_row = ttk.Frame(container)
        btn_row.pack(anchor="w")

        ttk.Button(
            btn_row,
            text="Set / Change",
            command=set_tmdb_key
        ).pack(side="left")

        ttk.Button(
            btn_row,
            text="Remove",
            command=remove_tmdb_key
        ).pack(side="left", padx=(8, 0))

        # -------- LOCAL POSTER --------
    def load_local_poster(self):
        p = filedialog.askopenfilename(
            filetypes=[("Images", "*.png *.jpg *.jpeg *.webp")]
        )
        if not p:
            return

        img = Image.open(p).convert("RGBA")
        self.selected_poster_image = img
        self.poster_orientation = "horizontal" if img.width > img.height else "vertical"
        self.update_crop_labels()
        self.current_game_title = os.path.splitext(os.path.basename(p))[0]
        self.render_with_current_template()

    # -------- RENDER --------

    def render_with_current_template(self):

        if self.crop_mode.get() == "manual":
            self.crop_slider.pack(fill="x", padx=10)
        else:
            self.crop_slider.pack_forget()

        cfg = TEMPLATES[self.template_var.get()]

        def crop(img, w, h):
            mode = self.crop_mode.get()

            if self.poster_orientation == "horizontal":
                if mode == "top":
                    return cover_image_left(img, w, h)
                if mode == "bottom":
                    return cover_image_right(img, w, h)
                if mode == "manual":
                    return cover_image_manual_x(img, w, h, self.crop_offset.get())
                return cover_image(img, w, h)
            else:
                if mode == "top":
                    return cover_image_top(img, w, h)
                if mode == "bottom":
                    return cover_image_bottom(img, w, h)
                if mode == "manual":
                    return cover_image_manual(img, w, h, self.crop_offset.get())
                return cover_image(img, w, h)

        # Template 6 – full poster with rounded corners (no base template, no logo)
        if cfg.get("mode") == "full-poster-rounded":
            if not self.selected_poster_image:
                return

            w = cfg["size"]["w"]
            h = cfg["size"]["h"]

            poster = crop(self.selected_poster_image, w, h)
            poster = apply_rounded_corners(
                poster,
                cfg.get("corner_radius", 24)
            )

            self.output_image = poster
            self.update_preview(poster)
            return
        template_img = Image.open(resource_path(cfg["image_path"])).convert("RGBA")

        # ---------------- TEMPLATE 3 ----------------
        if cfg["mode"] == "layered":
            base = Image.new("RGBA", template_img.size, (0, 0, 0, 0))

            if self.selected_poster_image:
                # Visible poster area = from poster_y to bottom
                visible_h = template_img.height - cfg["poster_y"]

                # Crop poster EXACTLY to visible area
                poster = crop(self.selected_poster_image, CLEAR_W, visible_h)

                # Center horizontally
                x = (template_img.width - CLEAR_W) // 2

                # Paste poster
                base.paste(poster, (x, cfg["poster_y"]), poster)

            # Overlay template artwork
            base.paste(template_img, (0, 0), template_img)

            # HARD ROUND FINAL IMAGE (prevents ALL bleed)
            base = apply_rounded_mask(base, radius=22)

            if self.logo_image or self.logo_path:
                apply_header_logo(base, self.logo_image or self.logo_path, cfg)

        # ---------------- TEMPLATE 4 & 5 ----------------
        elif cfg["mode"] == "framed-top-logo":
            base = template_img.copy()

            if self.selected_poster_image:
                poster = crop(self.selected_poster_image, T4_POSTER_W, T4_POSTER_H)
                x = (base.width - T4_POSTER_W) // 2
                base.paste(poster, (x, T4_POSTER_Y), poster)

            if self.logo_image or self.logo_path:
                apply_top_center_logo(base, self.logo_image or self.logo_path, cfg)

        # ---------------- TEMPLATE 1 & 2 ----------------
        else:
            base = template_img.copy()

            if self.logo_image or self.logo_path:
                apply_footer_logo(base, self.logo_image or self.logo_path, cfg)

            if self.selected_poster_image:
                c = cfg["center"]
                poster = crop(self.selected_poster_image, c["w"], c["h"])
                base.paste(poster, (c["x"], c["y"]), poster)

        self.output_image = base
        self.update_preview(base)

    def update_preview(self, base):
        w = self.preview_label.winfo_width()
        h = self.preview_label.winfo_height()
        if w <= 1 or h <= 1:
            return

        scale = min(w / base.width, h / base.height)
        img = base.resize(
            (int(base.width * scale), int(base.height * scale)),
            Image.LANCZOS
        )
        self.preview_image = ImageTk.PhotoImage(img)
        self.preview_label.configure(image=self.preview_image)

    # -------- SEARCH (SteamGridDB + TMDB) --------

    def search(self):
        query = self.game_entry.get().strip()
        if not query:
            return

        # invalidate previous searches
        self.search_id += 1
        current_search_id = self.search_id

        if self.source_var.get() == "system":
            if not (
                    (self.icon_pack_dir and os.path.isdir(self.icon_pack_dir)) or
                    self.search_cached_logos.get()
            ):
                return

            self.show_loading()

            threading.Thread(
                target=self.fetch_system_icons_thread,
                args=(query, current_search_id),
                daemon=True
            ).start()
            return

        # SteamGridDB (default)
        if not hasattr(self, "source_var") or self.source_var.get() == "steam":
            if not self.ensure_api_key("steamgriddb"):
                return

            games = search_games(query)
            game = self.pick_game(games)
            if not game:
                return

            self.current_game_title = game["name"]
            self.show_loading()

            threading.Thread(
                target=self.fetch_steam_thumbs_thread,
                args=(game["id"], current_search_id),
                daemon=True
            ).start()

        # TMDB (movies + TV)
        else:
            if not self.ensure_api_key("tmdb"):
                return

            results = tmdb_search_multi(query)
            item = self.pick_tmdb_item(results)
            if not item:
                return

            title = item["title"]
            if item.get("year"):
                title += f" ({item['year']})"
            self.current_game_title = title

            self.show_loading()

            threading.Thread(
                target=self.fetch_tmdb_thumb_thread,
                args=(item, current_search_id),
                daemon=True
            ).start()

    def show_loading(self):
        for w in self.thumb_frame.winfo_children():
            if w not in (self.loading_label, self.placeholder_label):
                w.destroy()

        self.placeholder_label.grid_forget()
        self.thumb_imgs.clear()
        self.canvas.yview_moveto(0)

        self.loading_label.grid(
            row=0,
            column=0,
            columnspan=THUMBS_PER_ROW,
            pady=15
        )

    # -------- STEAMGRIDDB THUMBS --------

    def fetch_steam_thumbs_thread(self, game_id, search_id):
        grids = get_grids(game_id)
        vertical = [g for g in grids if g["width"] < g["height"]]

        for grid in vertical:
            if search_id != self.search_id:
                return
            try:
                r = requests.get(grid["url"], timeout=10)
                r.raise_for_status()
                self.after(
                    0,
                    lambda g=grid, d=r.content: self.add_steam_thumb_from_data(g, d)
                )
            except Exception:
                pass

        def finish():
            self.loading_label.grid_forget()
            if not self.thumb_imgs:
                self.placeholder_label.grid(
                    row=0,
                    column=0,
                    columnspan=THUMBS_PER_ROW,
                    pady=30
                )

        self.after(150, finish)

    def add_steam_thumb_from_data(self, grid, data):
        self.placeholder_label.grid_forget()

        i = len(self.thumb_imgs)
        img = Image.open(BytesIO(data)).convert("RGBA")

        # Use vertical poster thumbnails (same as TMDB)
        img = img.resize((THUMB_W, THUMB_H), Image.LANCZOS)

        tk_img = ImageTk.PhotoImage(img)
        self.thumb_imgs.append(tk_img)

        ttk.Button(
            self.thumb_frame,
            image=tk_img,
            command=lambda g=grid: self.apply_steam_poster(g)
        ).grid(
            row=(i // THUMBS_PER_ROW) + 1,
            column=i % THUMBS_PER_ROW,
            padx=5,
            pady=5
        )

    def apply_steam_poster(self, grid):
        poster = Image.open(
            BytesIO(requests.get(grid["url"]).content)
        ).convert("RGBA")

        self.selected_poster_image = poster
        self.poster_orientation = "horizontal" if poster.width > poster.height else "vertical"
        self.update_crop_labels()
        self.render_with_current_template()

    # -------- TMDB THUMBS --------

    def pick_tmdb_item(self, items):
        d = tk.Toplevel(self)
        d.title("Select Movie / TV Show")
        d.geometry("520x420")
        d.grab_set()

        lb = tk.Listbox(d)
        lb.pack(fill="both", expand=True)

        for item in items:
            label = item["title"]
            if item.get("year"):
                label += f" ({item['media_type'].upper()}, {item['year']})"
            lb.insert(tk.END, label)

        lb.selection_set(0)
        result = {"item": None}

        def confirm():
            if lb.curselection():
                result["item"] = items[lb.curselection()[0]]
            d.destroy()

        ttk.Button(d, text="Select", command=confirm).pack()
        d.wait_window()
        return result["item"]

    def fetch_tmdb_thumb_thread(self, item, search_id):
        try:
            posters = tmdb_get_posters(item)

            for poster in posters:
                if search_id != self.search_id:
                    return

                path = poster.get("file_path")
                if not path:
                    continue

                url = TMDB_IMG_BASE + path
                r = requests.get(url, timeout=10)
                r.raise_for_status()

                self.after(
                    0,
                    lambda d=r.content: self.add_tmdb_thumb_from_data(d)
                )

        except Exception:
            pass

        def finish():
            self.loading_label.grid_forget()
            if not self.thumb_imgs:
                self.placeholder_label.grid(
                    row=0,
                    column=0,
                    columnspan=THUMBS_PER_ROW,
                    pady=30
                )

        self.after(150, finish)

    def add_tmdb_thumb_from_data(self, data):
        self.placeholder_label.grid_forget()

        i = len(self.thumb_imgs)
        img = Image.open(BytesIO(data)).convert("RGBA")
        img = img.resize((THUMB_W, THUMB_H), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(img)
        self.thumb_imgs.append(tk_img)

        ttk.Button(
            self.thumb_frame,
            image=tk_img,
            command=lambda d=data: self.apply_tmdb_poster(d)
        ).grid(
            row=(i // THUMBS_PER_ROW) + 1,
            column=i % THUMBS_PER_ROW,
            padx=5,
            pady=5
        )

    def apply_tmdb_poster(self, data):
        poster = Image.open(BytesIO(data)).convert("RGBA")
        self.selected_poster_image = poster
        self.poster_orientation = "vertical"
        self.update_crop_labels()
        self.render_with_current_template()

    def fetch_system_icons_thread(self, query, search_id):
        results = []

        # Search system logo pack
        if self.icon_pack_dir and os.path.isdir(self.icon_pack_dir):
            results.extend(
                search_system_icons(query, self.icon_pack_dir)
            )

        # Search cached web logos
        if self.search_cached_logos.get() and os.path.isdir(WEB_LOGO_DIR):
            results.extend(
                search_system_icons(query, WEB_LOGO_DIR)
            )

        for icon_path in results:
            if search_id != self.search_id:
                return

            try:
                with open(icon_path, "rb") as f:
                    data = f.read()

                self.after(
                    0,
                    lambda d=data, p=icon_path: self.add_system_icon_thumb(d, p)
                )
            except Exception:
                pass

        self.after(150, self.finish_thumb_load)

    def add_system_icon_thumb(self, data, path):
        self.placeholder_label.grid_forget()

        i = len(self.thumb_imgs)
        img = Image.open(BytesIO(data)).convert("RGBA")

        # Square system icon thumbnails
        img = fit_inside(img, ICON_THUMB_SIZE, ICON_THUMB_SIZE)

        tk_img = ImageTk.PhotoImage(img)
        self.thumb_imgs.append(tk_img)

        ttk.Button(
            self.thumb_frame,
            image=tk_img,
            command=lambda p=path: self.apply_system_icon(p)
        ).grid(
            row=(i // THUMBS_PER_ROW) + 1,
            column=i % THUMBS_PER_ROW,
            padx=5,
            pady=5
        )

    def apply_system_icon(self, path):
        self.logo_image = Image.open(path).convert("RGBA")
        self.logo_path = None
        self.render_with_current_template()

    def finish_thumb_load(self):
        self.loading_label.grid_forget()

        if not self.thumb_imgs:
            self.placeholder_label.grid(
                row=0,
                column=0,
                columnspan=THUMBS_PER_ROW,
                pady=30
            )

    # -------- OUTPUT --------

    def choose_output_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir = path
            save_output_dir(path)

            self.output_dir_btn.config(text="Change Output Folder")

            self.show_open_folder_button()
            self.show_status("Output folder set")

    def open_output_dir(self):
        try:
            if sys.platform.startswith("win"):
                os.startfile(self.output_dir)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", self.output_dir])
            else:
                subprocess.Popen(["xdg-open", self.output_dir])
        except Exception as e:
            messagebox.showerror("Error", f"Could not open folder:\n{e}")

    def update_output_folder_button(self):
        if self.output_dir and os.path.isdir(self.output_dir):
            if not self.open_folder_btn.winfo_ismapped():
                self.open_folder_btn.pack(side="left", padx=10)
        else:
            if self.open_folder_btn.winfo_ismapped():
                self.open_folder_btn.pack_forget()

    def show_status(self, text):
        self.status_label.config(text=text)
        if self.status_after_id:
            self.after_cancel(self.status_after_id)
        self.status_after_id = self.after(
            3000,
            lambda: self.status_label.config(text="")
        )

    def save(self):
        if not self.output_image or not self.output_dir:
            return

        name = sanitize_filename(self.current_game_title or "nfc_card")
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{name}_{ts}.png"

        self.output_image.save(os.path.join(self.output_dir, filename))
        self.show_status("Image saved")

    def save_as(self):
        if not self.output_image:
            return

        default_name = sanitize_filename(self.current_game_title or "nfc_card")
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        file_path = filedialog.asksaveasfilename(
            defaultextension=".png",
            initialfile=f"{default_name}_{ts}.png",
            filetypes=[("PNG Image", "*.png")]
        )

        if not file_path:
            return

        try:
            self.output_image.save(file_path)
            self.show_status("Image saved")
        except Exception as e:
            messagebox.showerror(
                "Error",
                f"Failed to save image:\n{e}"
            )

    def pick_game(self, games):
        d = tk.Toplevel(self)
        d.title("Select Game")
        d.geometry("520x420")
        d.grab_set()

        lb = tk.Listbox(d)
        lb.pack(fill="both", expand=True)

        for g in games:
            lb.insert(tk.END, g["name"])

        lb.selection_set(0)

        result = {"game": None}

        def confirm():
            if lb.curselection():
                result["game"] = games[lb.curselection()[0]]
            d.destroy()

        ttk.Button(d, text="Select", command=confirm).pack()
        d.wait_window()
        return result["game"]

    def load_logo(self):
        p = filedialog.askopenfilename(filetypes=[("PNG", "*.png")])
        if p:
            self.logo_image = Image.open(p).convert("RGBA")
            self.logo_path = None
            self.render_with_current_template()

    def ask_url(self, title):
        d = tk.Toplevel(self)
        d.title(title)
        d.geometry("520x150")
        d.grab_set()

        ttk.Label(d, text=title).pack(pady=10)

        url_var = tk.StringVar()
        e = ttk.Entry(d, textvariable=url_var, width=65)
        e.pack(padx=10)
        e.focus()

        result = {"url": None}

        def confirm(event=None):
            result["url"] = url_var.get().strip()
            d.destroy()

        e.bind("<Return>", confirm)

        ttk.Button(d, text="Load", command=confirm).pack(pady=10)

        d.wait_window()
        return result["url"]

    def ask_text_input(self, title, prompt):
        d = tk.Toplevel(self)
        d.title(title)
        d.geometry("520x160")
        d.transient(self)
        d.grab_set()

        ttk.Label(d, text=prompt).pack(pady=10)

        val = tk.StringVar()
        e = ttk.Entry(d, textvariable=val, width=60)
        e.pack(padx=10)
        e.focus()

        result = {"value": None}

        def confirm(event=None):
            result["value"] = val.get().strip()
            d.destroy()

        e.bind("<Return>", confirm)

        ttk.Button(d, text="Save", command=confirm).pack(pady=10)

        d.wait_window()
        return result["value"]

    def load_logo_from_url(self):
        url = self.ask_url("Enter System Logo URL")
        if not url:
            return

        try:
            img = load_image_from_url(url)
            self.logo_image = maybe_cache_web_image(img, url, kind="logo")
            self.logo_path = None
            self.render_with_current_template()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load logo:\n{e}")

    def load_poster_from_url(self):
        url = self.ask_url("Enter Poster Image URL")
        if not url:
            return

        try:
            img = load_image_from_url(url)

            # ONLY web images are cached (posters go to web-images/posters)
            self.selected_poster_image = maybe_cache_web_image(
                img, url, kind="poster"
            )

            self.poster_orientation = (
                "horizontal" if img.width > img.height else "vertical"
            )
            self.update_crop_labels()

            self.current_game_title = os.path.splitext(
                os.path.basename(url.split("?")[0])
            )[0]

            self.render_with_current_template()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to load poster:\n{e}")


# ---------------- RUN ----------------

if __name__ == "__main__":
    App().mainloop()
