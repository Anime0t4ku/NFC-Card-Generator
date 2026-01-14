import requests
from PIL import Image, ImageTk
from io import BytesIO
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
import os
import threading
import time
import sys
import subprocess

# ---------------- CONFIG ----------------

CONFIG_FILE = "config.json"

CLEAR_W = 609
CLEAR_H = 840

TEMPLATES = {
    "Template 1": {
        "image_path": "templates/template_1.png",
        "center": {"x": 10, "y": 59, "w": 597, "h": 855},
        "footer": {"height": 90, "logo_height": 46, "logo_margin": 25},
        "mode": "framed"
    },

    # TEMPLATE 2 – FINAL, LOCKED
    "Template 2": {
        "image_path": "templates/template_2.png",
        "center": {"x": 14, "y": 63, "w": 591, "h": 849},
        "footer": {"height": 90, "logo_height": 46, "logo_margin": 25},
        "mode": "framed"
    },

    # TEMPLATE 3 – FINAL WITH MAX WIDTH SAFETY
    "Template 3": {
        "image_path": "templates/template_3.png",
        "poster_y": 120,
        "header_logo": {
            "height": 63,
            "max_width": 250,   # prevents overlap with NFC logo
            "top_margin": 62,
            "left_margin": 24
        },
        "mode": "layered"
    }
}

THUMB_W = 160
THUMB_H = 240
THUMBS_PER_ROW = 3
TEMPLATE_THUMB_W = 140

PREVIEW_MIN_W = 340
PREVIEW_MIN_H = 520

API_KEY = None

# ---------------- CONFIG HELPERS ----------------

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def load_api_key():
    return load_config().get("steamgriddb_api_key")

def save_api_key(key):
    cfg = load_config()
    cfg["steamgriddb_api_key"] = key
    save_config(cfg)

def load_output_dir():
    return load_config().get("output_directory")

def save_output_dir(path):
    cfg = load_config()
    cfg["output_directory"] = path
    save_config(cfg)

def headers():
    return {"Authorization": f"Bearer {API_KEY}"}

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

# ---------------- IMAGE HELPERS ----------------

def cover_image(img, w, h):
    ratio = max(w / img.width, h / img.height)
    resized = img.resize(
        (int(img.width * ratio), int(img.height * ratio)),
        Image.LANCZOS
    )
    x = (resized.width - w) // 2
    y = (resized.height - h) // 2
    return resized.crop((x, y, x + w, y + h))

def fit_to_width(img, target_width):
    scale = target_width / img.width
    return img.resize(
        (target_width, int(img.height * scale)),
        Image.LANCZOS
    )

def apply_footer_logo(base, logo_path, cfg):
    logo = Image.open(logo_path).convert("RGBA")
    f = cfg["footer"]

    scale = f["logo_height"] / logo.height
    logo = logo.resize(
        (int(logo.width * scale), f["logo_height"]),
        Image.LANCZOS
    )

    x = f["logo_margin"]
    y = base.height - f["height"] + (f["height"] - logo.height) // 2
    base.paste(logo, (x, y), logo)

def apply_header_logo(base, logo_path, cfg):
    logo = Image.open(logo_path).convert("RGBA")
    h = cfg["header_logo"]

    # Scale to fixed height first
    scale_h = h["height"] / logo.height
    logo = logo.resize(
        (int(logo.width * scale_h), h["height"]),
        Image.LANCZOS
    )

    # Clamp width if needed (never increases height)
    max_w = h.get("max_width")
    if max_w and logo.width > max_w:
        scale_w = max_w / logo.width
        logo = logo.resize(
            (max_w, int(logo.height * scale_w)),
            Image.LANCZOS
        )

    x = h["left_margin"]
    y = h["top_margin"]
    base.paste(logo, (x, y), logo)

# ---------------- GUI ----------------

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("NFC Card Generator")
        self.geometry("1200x900")
        self.minsize(1000, 700)

        self.logo_path = None
        self.output_image = None
        self.output_dir = load_output_dir()
        self.template_var = tk.StringVar(value="Template 1")
        self.selected_poster_image = None

        self.template_imgs = {}
        self.thumb_imgs = []
        self.preview_image = None
        self.status_after_id = None

        self.build_ui()
        self.after(100, self.init_api_key)

        if self.output_dir and os.path.isdir(self.output_dir):
            self.show_open_folder_button()

    # -------- API KEY --------

    def init_api_key(self):
        global API_KEY
        API_KEY = load_api_key()
        while not API_KEY:
            key = self.ask_api_key()
            if not key:
                self.destroy()
                return
            save_api_key(key)
            API_KEY = key

    def ask_api_key(self):
        d = tk.Toplevel(self)
        d.title("SteamGridDB API Key")
        d.geometry("420x160")
        d.grab_set()

        ttk.Label(d, text="Enter your SteamGridDB API key").pack(pady=10)
        e = ttk.Entry(d, width=50)
        e.pack()

        ttk.Button(d, text="Save", command=lambda: (save_api_key(e.get()), d.destroy())).pack(pady=10)
        d.wait_window()
        return load_api_key()

    # -------- UI --------

    def build_template_selector(self):
        frame = ttk.LabelFrame(self, text="Select Template")
        frame.pack(pady=10)

        for name, cfg in TEMPLATES.items():
            img = Image.open(cfg["image_path"])
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
                command=self.refresh_preview
            ).pack(side="left", padx=8)

    def build_ui(self):
        self.build_template_selector()

        controls = ttk.Frame(self)
        controls.pack(pady=5)

        ttk.Button(controls, text="Upload System Logo", command=self.load_logo).pack(side="left", padx=5)
        ttk.Label(controls, text="Game:").pack(side="left")
        self.game_entry = ttk.Entry(controls, width=30)
        self.game_entry.pack(side="left", padx=5)
        ttk.Button(controls, text="Search", command=self.search).pack(side="left")

        main = ttk.Frame(self)
        main.pack(fill="both", expand=True)

        main.columnconfigure(0, weight=1)
        main.columnconfigure(1, weight=0)
        main.columnconfigure(2, weight=1)
        main.rowconfigure(0, weight=1)
        main.rowconfigure(1, weight=0)

        selector_container = ttk.Frame(main)
        selector_container.grid(row=0, column=1, padx=20, sticky="n")

        self.canvas = tk.Canvas(selector_container, width=520, height=750)
        self.canvas.pack(side="left")

        sb = ttk.Scrollbar(selector_container, orient="vertical", command=self.canvas.yview)
        sb.pack(side="left", fill="y")
        self.canvas.configure(yscrollcommand=sb.set)

        self.thumb_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((260, 0), window=self.thumb_frame, anchor="n")

        self.thumb_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.loading_label = ttk.Label(self.thumb_frame, text="Loading images…", foreground="gray")

        preview = ttk.Frame(main)
        preview.grid(row=0, column=2, padx=40, sticky="nsew")

        ttk.Label(preview, text="Preview").pack(anchor="n")

        preview_frame = ttk.Frame(preview, width=PREVIEW_MIN_W, height=PREVIEW_MIN_H)
        preview_frame.pack(expand=True)
        preview_frame.pack_propagate(False)

        self.preview_label = ttk.Label(preview_frame)
        self.preview_label.pack(expand=True, fill="both")
        self.preview_label.bind("<Configure>", self.on_preview_resize)

        bottom = ttk.Frame(main)
        bottom.grid(row=1, column=0, columnspan=3, pady=10)

        ttk.Button(bottom, text="Set Output Folder", command=self.choose_output_dir).pack(side="left", padx=10)

        self.open_folder_btn = ttk.Button(bottom, text="Open Output Folder", command=self.open_output_dir)
        ttk.Button(bottom, text="Save Image", command=self.save).pack(side="left")

        self.status_label = ttk.Label(bottom, text="", foreground="green")
        self.status_label.pack(side="left", padx=15)

    # -------- RENDERING --------

    def render_with_current_template(self):
        cfg = TEMPLATES[self.template_var.get()]
        template_img = Image.open(cfg["image_path"]).convert("RGBA")

        if cfg["mode"] == "layered":
            base = Image.new("RGBA", template_img.size, (0, 0, 0, 0))

            if self.selected_poster_image:
                poster = fit_to_width(self.selected_poster_image, CLEAR_W)
                x = (template_img.width - poster.width) // 2
                y = cfg["poster_y"]
                base.paste(poster, (x, y))

            base.paste(template_img, (0, 0), template_img)

            if self.logo_path:
                apply_header_logo(base, self.logo_path, cfg)

        else:
            base = template_img.copy()

            if self.logo_path:
                apply_footer_logo(base, self.logo_path, cfg)

            if self.selected_poster_image:
                c = cfg["center"]
                poster = cover_image(self.selected_poster_image, c["w"], c["h"])
                base.paste(poster, (c["x"], c["y"]), poster)

        self.output_image = base
        self.update_preview(base)

    def refresh_preview(self):
        self.render_with_current_template()

    def on_preview_resize(self, event):
        if self.output_image:
            self.update_preview(self.output_image)

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

    # -------- STEAMGRIDDB --------

    def search(self):
        if not self.logo_path:
            messagebox.showerror("Error", "Upload a system logo first")
            return

        query = self.game_entry.get().strip()
        if not query:
            return

        games = search_games(query)
        game = self.pick_game(games)
        if not game:
            return

        self.show_loading()
        threading.Thread(
            target=self.fetch_thumbs_thread,
            args=(game["id"],),
            daemon=True
        ).start()

    def show_loading(self):
        for w in self.thumb_frame.winfo_children():
            if w is not self.loading_label:
                w.destroy()
        self.thumb_imgs.clear()
        self.canvas.yview_moveto(0)
        self.loading_label.grid(row=0, column=0, columnspan=THUMBS_PER_ROW, pady=15)

    def fetch_thumbs_thread(self, game_id):
        grids = get_grids(game_id)
        vertical = [g for g in grids if g["width"] < g["height"]]

        for grid in vertical:
            try:
                r = requests.get(grid["url"], timeout=10)
                r.raise_for_status()
                self.after(0, lambda g=grid, d=r.content: self.add_thumb_from_data(g, d))
            except Exception:
                pass

        self.after(150, self.loading_label.grid_forget)

    def add_thumb_from_data(self, grid, data):
        i = len(self.thumb_imgs)
        img = Image.open(BytesIO(data)).convert("RGBA")
        img = img.resize((THUMB_W, THUMB_H), Image.LANCZOS)
        tk_img = ImageTk.PhotoImage(img)
        self.thumb_imgs.append(tk_img)

        ttk.Button(
            self.thumb_frame,
            image=tk_img,
            command=lambda g=grid: self.apply_poster(g)
        ).grid(
            row=(i // THUMBS_PER_ROW) + 1,
            column=i % THUMBS_PER_ROW,
            padx=5,
            pady=5
        )

    def apply_poster(self, grid):
        poster = Image.open(BytesIO(requests.get(grid["url"]).content)).convert("RGBA")
        self.selected_poster_image = poster
        self.render_with_current_template()

    # -------- OUTPUT --------

    def show_open_folder_button(self):
        if not self.open_folder_btn.winfo_ismapped():
            self.open_folder_btn.pack(side="left", padx=10)

    def choose_output_dir(self):
        path = filedialog.askdirectory()
        if path:
            self.output_dir = path
            save_output_dir(path)
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

    def show_status(self, text):
        self.status_label.config(text=text)
        if self.status_after_id:
            self.after_cancel(self.status_after_id)
        self.status_after_id = self.after(3000, lambda: self.status_label.config(text=""))

    def save(self):
        if not self.output_image or not self.output_dir:
            return

        filename = f"nfc_card_{int(time.time())}.png"
        self.output_image.save(os.path.join(self.output_dir, filename))
        self.show_status("Image saved")

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
            self.logo_path = p
            self.render_with_current_template()

# ---------------- RUN ----------------

if __name__ == "__main__":
    App().mainloop()
