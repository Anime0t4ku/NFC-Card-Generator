import json
import os
import re
import sys


def get_base_dir():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


BASE_DIR = get_base_dir()
CONFIG_FILE = os.path.join(BASE_DIR, 'config.json')
WEB_IMAGE_DIR = os.path.join(BASE_DIR, 'web-images')
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
    return get_value('output_directory')


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
