import json
import os
import re
import sys


APP_NAME = 'NFC Card Generator'


def is_macos_binary():
    return sys.platform == 'darwin' and getattr(sys, 'frozen', False)


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def get_app_support_dir():
    return os.path.join(os.path.expanduser('~'), 'Library', 'Application Support', APP_NAME)


def get_data_dir():
    if is_macos_binary():
        return get_app_support_dir()
    return get_base_dir()


def get_default_output_dir():
    if is_macos_binary():
        return os.path.join(DATA_DIR, 'output')
    return None


def ensure_dir(path):
    if path:
        os.makedirs(path, exist_ok=True)


BASE_DIR = get_base_dir()
DATA_DIR = get_data_dir()
CONFIG_FILE = os.path.join(DATA_DIR, 'config.json')
WEB_IMAGE_DIR = os.path.join(DATA_DIR, 'web-images')
WEB_POSTER_DIR = os.path.join(WEB_IMAGE_DIR, 'posters')
WEB_LOGO_DIR = os.path.join(WEB_IMAGE_DIR, 'logos')


def resource_path(relative_path):
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(BASE_DIR, relative_path)


def sanitize_filename(name):
    name = re.sub(r'[<>:"/\\|?*]', '', name or '')
    return re.sub(r'\s+', ' ', name).strip() or 'nfc_card'


def load_config():
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg):
    ensure_dir(os.path.dirname(CONFIG_FILE))
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(cfg, f, indent=2)


def get_value(key, default=None):
    return load_config().get(key, default)


def set_value(key, value):
    cfg = load_config()
    if value is None:
        cfg.pop(key, None)
    else:
        cfg[key] = value
    save_config(cfg)


def load_api_key(service='steamgriddb'):
    return get_value(f'{service}_api_key')


def save_api_key(key, service='steamgriddb'):
    set_value(f'{service}_api_key', key or None)


def load_output_dir():
    path = get_value('output_directory')
    if path:
        return path

    default_path = get_default_output_dir()
    if default_path:
        ensure_dir(default_path)
    return default_path


def save_output_dir(path):
    set_value('output_directory', path)


def load_icon_pack_dir():
    return get_value('icon_pack_directory')


def save_icon_pack_dir(path):
    set_value('icon_pack_directory', path)


def load_cache_posters():
    return bool(get_value('cache_web_posters', False))


def save_cache_posters(value):
    set_value('cache_web_posters', bool(value))


def load_cache_logos():
    return bool(get_value('cache_web_logos', False))


def save_cache_logos(value):
    set_value('cache_web_logos', bool(value))


def load_search_cached_logos():
    return bool(get_value('search_cached_web_logos', False))


def save_search_cached_logos(value):
    set_value('search_cached_web_logos', bool(value))


def load_favourite_logos():
    return get_value('favourite_logos', [])


def save_favourite_logos(paths):
    set_value('favourite_logos', sorted(paths))


def add_favourite_logo(path):
    favs = set(load_favourite_logos())
    favs.add(path)
    save_favourite_logos(list(favs))


def remove_favourite_logo(path):
    favs = set(load_favourite_logos())
    favs.discard(path)
    save_favourite_logos(list(favs))
