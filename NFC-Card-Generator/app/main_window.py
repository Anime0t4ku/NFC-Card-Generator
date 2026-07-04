import os
import sys
import subprocess
from datetime import datetime
from io import BytesIO

import requests
from PIL import Image
from PyQt6.QtCore import Qt, QSize, QThread, pyqtSignal, QTimer, QUrl
from PyQt6.QtGui import QPixmap, QImage, QDesktopServices, QIcon
from PyQt6.QtWidgets import (
    QApplication, QButtonGroup, QCheckBox, QComboBox, QDialog, QFileDialog,
    QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QMainWindow, QMenu, QMessageBox, QPushButton, QRadioButton,
    QScrollArea, QSizePolicy, QSlider, QToolButton, QVBoxLayout, QWidget
)

from app.config import (
    resource_path, sanitize_filename, load_api_key, save_api_key,
    load_output_dir, save_output_dir, load_icon_pack_dir, save_icon_pack_dir,
    load_cache_posters, save_cache_posters, load_cache_logos, save_cache_logos,
    load_search_cached_logos, save_search_cached_logos, load_favourite_logos,
    add_favourite_logo, remove_favourite_logo
)
from app.image_engine import (
    TEMPLATES, TEMPLATE_THUMB_W, TEMPLATE_THUMB_H, THUMB_W, THUMB_H,
    ICON_THUMB_SIZE, fit_inside, load_image_from_url, load_image_from_bytes,
    load_image_from_file, maybe_cache_web_image, render_card, render_nfc_print_sheet
)
from app import services


class Worker(QThread):
    item = pyqtSignal(object)
    done = pyqtSignal(object)
    error = pyqtSignal(object)

    def __init__(self, mode, payload, parent=None):
        super().__init__(parent)
        self.mode = mode
        self.payload = payload
        self.search_id = payload.get('search_id', 0)

    def run(self):
        try:
            if self.mode == 'steam':
                grids = services.get_grids(self.payload['game_id'])
                count = 0
                for grid in [g for g in grids if g.get('width', 0) < g.get('height', 0)]:
                    if self.isInterruptionRequested():
                        return
                    try:
                        r = requests.get(grid['url'], timeout=15)
                        r.raise_for_status()
                        self.item.emit({'search_id': self.search_id, 'kind': 'steam', 'grid': grid, 'data': r.content})
                        count += 1
                    except Exception:
                        pass
                self.done.emit({'search_id': self.search_id, 'count': count})
            elif self.mode == 'tmdb':
                posters = services.tmdb_get_posters(self.payload['item'])
                count = 0
                for poster in posters:
                    if self.isInterruptionRequested():
                        return
                    path = poster.get('file_path')
                    if not path:
                        continue
                    try:
                        url = services.TMDB_IMG_BASE + path
                        r = requests.get(url, timeout=15)
                        r.raise_for_status()
                        self.item.emit({'search_id': self.search_id, 'kind': 'tmdb', 'data': r.content})
                        count += 1
                    except Exception:
                        pass
                self.done.emit({'search_id': self.search_id, 'count': count})
            elif self.mode == 'system':
                paths, total = services.search_system_logos(
                    self.payload['query'],
                    self.payload.get('icon_pack_dir'),
                    self.payload.get('search_cached', False),
                    self.payload.get('indices'),
                )
                count = 0
                for path in paths:
                    if self.isInterruptionRequested():
                        return
                    try:
                        with open(path, 'rb') as f:
                            self.item.emit({'search_id': self.search_id, 'kind': 'system', 'data': f.read(), 'path': path})
                        count += 1
                    except Exception:
                        pass
                self.done.emit({'search_id': self.search_id, 'count': count, 'total': total})
        except Exception as e:
            self.error.emit({'search_id': self.search_id, 'message': str(e)})
            self.done.emit({'search_id': self.search_id, 'count': 0})


def pil_to_pixmap(img):
    img = img.convert('RGBA')
    data = img.tobytes('raw', 'RGBA')
    qimg = QImage(data, img.width, img.height, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg.copy())


class SelectDialog(QDialog):
    def __init__(self, title, labels, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(520, 420)
        self.result_index = None
        layout = QVBoxLayout(self)
        self.list_widget = QListWidget()
        self.list_widget.addItems(labels)
        if labels:
            self.list_widget.setCurrentRow(0)
        layout.addWidget(self.list_widget)
        row = QHBoxLayout()
        select_btn = QPushButton('Select')
        cancel_btn = QPushButton('Cancel')
        row.addStretch(1)
        row.addWidget(select_btn)
        row.addWidget(cancel_btn)
        layout.addLayout(row)
        select_btn.clicked.connect(self.accept_selection)
        cancel_btn.clicked.connect(self.reject)
        self.list_widget.itemDoubleClicked.connect(lambda *_: self.accept_selection())

    def accept_selection(self):
        row = self.list_widget.currentRow()
        if row >= 0:
            self.result_index = row
            self.accept()


class TextInputDialog(QDialog):
    def __init__(self, title, prompt, value='', parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(540, 150)
        self.value = None
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(prompt))
        self.entry = QLineEdit(value)
        layout.addWidget(self.entry)
        row = QHBoxLayout()
        ok = QPushButton('OK')
        cancel = QPushButton('Cancel')
        row.addStretch(1)
        row.addWidget(ok)
        row.addWidget(cancel)
        layout.addLayout(row)
        ok.clicked.connect(self.accept_value)
        cancel.clicked.connect(self.reject)
        self.entry.returnPressed.connect(self.accept_value)

    def accept_value(self):
        self.value = self.entry.text().strip()
        self.accept()


class MainWindow(QMainWindow):
    ALL_CORNERS = ['top-left', 'top-right', 'bottom-left', 'bottom-right']

    def __init__(self):
        super().__init__()
        self.setWindowTitle('NFC Card Generator v3.2.0')
        self.resize(1200, 1000)
        self.setMinimumSize(1000, 700)
        icon_path = resource_path('Icon.png')
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.logo_image = None
        self.logo_path = None
        self.logo_name = None
        self.selected_poster_image = None
        self.poster_orientation = 'vertical'
        self.current_game_title = None
        self.output_image = None
        self.output_dir = load_output_dir()
        self.icon_pack_dir = load_icon_pack_dir()
        self.template_name = 'Black with Pins'
        self.source = 'steam'
        self.system_icon_indices = {}
        self.favourite_logos = set(load_favourite_logos())
        self.worker = None
        self.workers = []
        self.search_id = 0
        self.thumb_refs = []
        self.source_state = {
            'steam': {'query': '', 'thumbs': []},
            'tmdb': {'query': '', 'thumbs': []},
            'system': {'query': '', 'thumbs': []},
            'favs': {'query': '', 'thumbs': []},
        }

        self.build_ui()
        self.refresh_placeholder_text()
        self.update_output_folder_button()
        self.render_current()

    def build_ui(self):
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)
        self.setCentralWidget(central)

        self.build_template_selector(root)
        self.build_crop_row(root)
        self.build_controls_row(root)

        # Center the combined thumbnail/results + preview block.
        main_outer = QHBoxLayout()
        main_outer.setContentsMargins(0, 0, 0, 0)
        main_outer.setSpacing(0)
        root.addLayout(main_outer, 1)

        main_outer.addStretch(1)

        main_widget = QWidget()
        main = QHBoxLayout(main_widget)
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(30)

        main_outer.addWidget(main_widget, 0, Qt.AlignmentFlag.AlignHCenter)
        main_outer.addStretch(1)

        selector_container = QWidget()
        selector_layout = QVBoxLayout(selector_container)
        selector_layout.setContentsMargins(0, 0, 0, 0)
        self.thumb_scroll = QScrollArea()
        self.thumb_scroll.setWidgetResizable(True)
        self.thumb_scroll.setMinimumWidth(540)
        self.thumb_scroll.setMaximumWidth(570)
        self.thumb_widget = QWidget()
        self.thumb_grid = QGridLayout(self.thumb_widget)
        self.thumb_grid.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignHCenter)
        self.thumb_scroll.setWidget(self.thumb_widget)
        selector_layout.addWidget(self.thumb_scroll)
        main.addWidget(selector_container, 0, Qt.AlignmentFlag.AlignHCenter)

        preview_container = QWidget()
        preview_container.setMinimumWidth(380)
        preview_layout = QVBoxLayout(preview_container)
        preview_layout.setContentsMargins(0, 0, 0, 0)
        preview_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        preview_title = QLabel('Preview')
        preview_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview_layout.addWidget(preview_title, 0, Qt.AlignmentFlag.AlignHCenter)

        self.preview_label = QLabel()
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(260, 400)
        self.preview_label.setMaximumSize(340, 530)
        self.preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        preview_layout.addWidget(self.preview_label, 0, Qt.AlignmentFlag.AlignHCenter)
        preview_layout.addStretch(1)
        main.addWidget(preview_container, 0, Qt.AlignmentFlag.AlignHCenter)

        # Center bottom actions as a compact button row.
        bottom_outer = QHBoxLayout()
        bottom_outer.setContentsMargins(0, 0, 0, 0)
        root.addLayout(bottom_outer)

        bottom_outer.addStretch(1)

        bottom_widget = QWidget()
        bottom = QHBoxLayout(bottom_widget)
        bottom.setContentsMargins(0, 0, 0, 0)
        bottom.setSpacing(8)

        settings_btn = QPushButton('Settings')
        settings_btn.clicked.connect(self.open_settings)
        bottom.addWidget(settings_btn)

        save_btn = QPushButton('Save Image')
        save_btn.clicked.connect(self.save)
        bottom.addWidget(save_btn)

        save_as_btn = QPushButton('Save As…')
        save_as_btn.clicked.connect(self.save_as)
        bottom.addWidget(save_as_btn)

        pdf_btn = QPushButton('Create Print PDF')
        pdf_btn.clicked.connect(self.open_print_pdf_window)
        bottom.addWidget(pdf_btn)

        self.open_folder_btn = QPushButton('Open Output Folder')
        self.open_folder_btn.clicked.connect(self.open_output_dir)
        bottom.addWidget(self.open_folder_btn)

        bottom_outer.addWidget(bottom_widget, 0, Qt.AlignmentFlag.AlignHCenter)
        bottom_outer.addStretch(1)

        self.status_label = QLabel('')
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setStyleSheet('color: green;')
        root.addWidget(self.status_label, 0, Qt.AlignmentFlag.AlignHCenter)

    def build_template_selector(self, root):
        group = QGroupBox('Select Template')
        outer = QVBoxLayout(group)
        outer.setContentsMargins(8, 8, 8, 8)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(TEMPLATE_THUMB_H + 78)

        content = QWidget()
        row = QHBoxLayout(content)
        row.setContentsMargins(4, 4, 4, 4)
        row.setSpacing(10)
        row.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.template_group = QButtonGroup(self)
        self.template_group.setExclusive(True)

        for name, cfg in TEMPLATES.items():
            btn = QToolButton()
            btn.setCheckable(True)
            btn.setText(name)
            btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            btn.setIconSize(QSize(TEMPLATE_THUMB_W, TEMPLATE_THUMB_H))
            btn.setFixedSize(TEMPLATE_THUMB_W + 28, TEMPLATE_THUMB_H + 48)
            btn.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

            p = resource_path(cfg['image_path'])
            if os.path.exists(p):
                img = load_image_from_file(p)
                btn.setIcon(QIcon(pil_to_pixmap(fit_inside(img, TEMPLATE_THUMB_W, TEMPLATE_THUMB_H))))

            btn.setChecked(name == self.template_name)
            btn.toggled.connect(lambda checked, n=name: checked and self.on_template_changed(n))
            self.template_group.addButton(btn)
            row.addWidget(btn)

        scroll.setWidget(content)
        outer.addWidget(scroll)
        root.addWidget(group)

    def build_crop_row(self, root):
        row = QGridLayout()
        root.addLayout(row)

        row.setColumnStretch(0, 1)
        row.setColumnStretch(1, 0)
        row.setColumnStretch(2, 1)

        crop_group = QGroupBox('Poster Crop Mode')
        crop_layout = QHBoxLayout(crop_group)
        crop_layout.setContentsMargins(10, 8, 10, 8)

        self.crop_group = QButtonGroup(self)
        self.crop_buttons = {}

        for name in ['center', 'top', 'bottom', 'manual']:
            btn = QRadioButton(name.capitalize())
            btn.setChecked(name == 'center')
            btn.toggled.connect(lambda checked, m=name: checked and self.on_crop_changed())
            self.crop_group.addButton(btn)
            self.crop_buttons[name] = btn
            crop_layout.addWidget(btn)

        self.crop_slider = QSlider(Qt.Orientation.Horizontal)
        self.crop_slider.setRange(0, 1000)
        self.crop_slider.setFixedWidth(220)
        self.crop_slider.setVisible(False)
        self.crop_slider.valueChanged.connect(lambda *_: self.render_current())
        crop_layout.addWidget(self.crop_slider)

        row.addWidget(
            crop_group,
            0,
            1,
            Qt.AlignmentFlag.AlignHCenter
        )

        self.template9_group = QGroupBox('SV-001 Options')
        t9 = QHBoxLayout(self.template9_group)
        t9.setContentsMargins(10, 8, 10, 8)

        self.nfc_color_black = QRadioButton('Black')
        self.nfc_color_white = QRadioButton('White')
        self.nfc_color_white.setChecked(True)

        self.nfc_color_black.toggled.connect(lambda *_: self.render_current())
        self.nfc_color_white.toggled.connect(lambda *_: self.render_current())

        t9.addWidget(QLabel('NFC Logo Color'))
        t9.addWidget(self.nfc_color_black)
        t9.addWidget(self.nfc_color_white)

        self.nfc_corner_combo = QComboBox()
        self.nfc_corner_combo.addItems(self.ALL_CORNERS)
        self.nfc_corner_combo.setCurrentText('top-right')
        self.nfc_corner_combo.currentTextChanged.connect(self.on_nfc_corner_change)

        self.system_corner_combo = QComboBox()
        self.system_corner_combo.addItems(self.ALL_CORNERS)
        self.system_corner_combo.setCurrentText('bottom-left')
        self.system_corner_combo.currentTextChanged.connect(lambda *_: self.render_current())

        t9.addWidget(QLabel('NFC Position'))
        t9.addWidget(self.nfc_corner_combo)
        t9.addWidget(QLabel('System Position'))
        t9.addWidget(self.system_corner_combo)

        self.template9_group.setVisible(False)

        row.addWidget(
            self.template9_group,
            0,
            2,
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

    def build_controls_row(self, root):
        outer = QHBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        root.addLayout(outer)

        outer.addStretch(1)

        row_widget = QWidget()
        row = QHBoxLayout(row_widget)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)

        self.controls_row = row

        logo_btn = QPushButton('System Logo ▼')
        logo_menu = QMenu(self)
        logo_menu.addAction('Import from file', self.load_logo)
        logo_menu.addAction('Import from URL', self.load_logo_from_url)
        logo_btn.setMenu(logo_menu)
        row.addWidget(logo_btn)

        poster_btn = QPushButton('Poster ▼')
        poster_menu = QMenu(self)
        poster_menu.addAction('Import from file', self.load_local_poster)
        poster_menu.addAction('Import from URL', self.load_poster_from_url)
        poster_btn.setMenu(poster_menu)
        row.addWidget(poster_btn)

        row.addWidget(QLabel('Source:'))

        self.source_group = QButtonGroup(self)
        self.source_buttons = {}

        for label, value in [('SteamGridDB', 'steam'), ('TMDB', 'tmdb')]:
            btn = QRadioButton(label)
            btn.setChecked(value == self.source)
            btn.toggled.connect(lambda checked, v=value: checked and self.on_source_change(v))
            self.source_group.addButton(btn)
            self.source_buttons[value] = btn
            row.addWidget(btn)

        self.rebuild_optional_source_buttons(row)

        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        row.addWidget(line)

        row.addWidget(QLabel('Search:'))

        self.search_entry = QLineEdit()
        self.search_entry.setFixedWidth(260)
        self.search_entry.returnPressed.connect(self.search)
        self.search_entry.textChanged.connect(lambda text: self.clear_btn.setEnabled(bool(text)))
        row.addWidget(self.search_entry)

        self.clear_btn = QPushButton('✕')
        self.clear_btn.setFixedWidth(30)
        self.clear_btn.setEnabled(False)
        self.clear_btn.clicked.connect(self.clear_search)
        row.addWidget(self.clear_btn)

        search_btn = QPushButton('Search')
        search_btn.clicked.connect(self.search)
        row.addWidget(search_btn)

        outer.addWidget(row_widget, 0, Qt.AlignmentFlag.AlignHCenter)
        outer.addStretch(1)

    def rebuild_optional_source_buttons(self, row=None):
        enabled = (self.icon_pack_dir and os.path.isdir(self.icon_pack_dir)) or load_search_cached_logos()
        if not enabled:
            return
        for label, value in [('System Logos', 'system'), ('⭐ Favourites', 'favs')]:
            if value in self.source_buttons:
                continue
            btn = QRadioButton(label)
            btn.toggled.connect(lambda checked, v=value: checked and self.on_source_change(v))
            self.source_group.addButton(btn)
            self.source_buttons[value] = btn
            if row:
                row.addWidget(btn)


    def next_search_id(self):
        self.search_id += 1
        return self.search_id

    def is_current_search(self, search_id):
        return search_id == self.search_id

    def on_template_changed(self, name):
        self.template_name = name
        self.template9_group.setVisible(TEMPLATES[name].get('mode') == 'layered-dual-corner')
        self.render_current()

    def get_crop_mode(self):
        for name, btn in self.crop_buttons.items():
            if btn.isChecked():
                return name
        return 'center'

    def on_crop_changed(self):
        self.crop_slider.setVisible(self.get_crop_mode() == 'manual')
        self.render_current()

    def on_nfc_corner_change(self):
        selected = self.nfc_corner_combo.currentText()
        current = self.system_corner_combo.currentText()
        available = [c for c in self.ALL_CORNERS if c != selected]
        self.system_corner_combo.blockSignals(True)
        self.system_corner_combo.clear()
        self.system_corner_combo.addItems(available)
        self.system_corner_combo.setCurrentText(current if current in available else available[0])
        self.system_corner_combo.blockSignals(False)
        self.render_current()

    def update_crop_labels(self):
        if self.poster_orientation == 'horizontal':
            self.crop_buttons['top'].setText('Left')
            self.crop_buttons['bottom'].setText('Right')
        else:
            self.crop_buttons['top'].setText('Top')
            self.crop_buttons['bottom'].setText('Bottom')

    def render_current(self):
        try:
            self.output_image = render_card(
                self.template_name,
                poster_image=self.selected_poster_image,
                logo_image=self.logo_image,
                crop_mode=self.get_crop_mode(),
                crop_offset=self.crop_slider.value(),
                poster_orientation=self.poster_orientation,
                nfc_logo_color='white' if self.nfc_color_white.isChecked() else 'black',
                nfc_corner=self.nfc_corner_combo.currentText(),
                system_corner=self.system_corner_combo.currentText(),
            )
            self.update_preview()
        except Exception as e:
            self.show_status(f'Render failed: {e}')

    def update_preview(self):
        if not self.output_image:
            return
        img = self.output_image.copy()
        available = self.preview_label.size()
        w = max(1, min(available.width(), 340))
        h = max(1, min(available.height(), 530))
        scale = min(w / img.width, h / img.height)
        preview = img.resize((max(1, int(img.width * scale)), max(1, int(img.height * scale))), Image.LANCZOS)
        self.preview_label.setPixmap(pil_to_pixmap(preview))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.update_preview)

    def clear_thumbs(self):
        while self.thumb_grid.count():
            item = self.thumb_grid.takeAt(0)
            widget = item.widget()
            if widget:
                widget.deleteLater()
        self.thumb_refs.clear()

    def set_placeholder(self, text):
        self.clear_thumbs()
        label = QLabel(text)
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setStyleSheet('color: gray;')
        self.thumb_grid.addWidget(label, 0, 0, 1, 3)

    def refresh_placeholder_text(self):
        if self.source == 'steam':
            self.set_placeholder('Search for a game to load posters\nor use "Poster ▼" to add your own image')
        elif self.source == 'tmdb':
            self.set_placeholder('Search for a movie or TV show to load posters\nor use "Poster ▼" to add your own image')
        elif self.source == 'system':
            self.set_placeholder('Search by platform or logo name\n(e.g. "arcade", "capcom", "nintendo")')
        else:
            self.show_favourite_logos()

    def on_source_change(self, source):
        self.next_search_id()
        self.source_state[self.source]['query'] = self.search_entry.text()
        self.source = source
        state = self.source_state[source]
        self.search_entry.blockSignals(True)
        self.search_entry.setText(state.get('query', ''))
        self.search_entry.blockSignals(False)
        self.clear_btn.setEnabled(bool(self.search_entry.text()))
        self.clear_thumbs()
        if source == 'favs':
            self.show_favourite_logos()
        elif state['thumbs']:
            for item in state['thumbs']:
                self.restore_thumb(source, item)
        else:
            self.refresh_placeholder_text()

    def clear_search(self):
        self.next_search_id()
        self.search_entry.clear()
        self.source_state[self.source]['query'] = ''
        self.source_state[self.source]['thumbs'] = []
        self.refresh_placeholder_text()

    def search(self):
        query = self.search_entry.text().strip()
        self.source_state[self.source]['query'] = query
        self.source_state[self.source]['thumbs'] = []
        if not query:
            return
        search_id = self.next_search_id()
        if self.source == 'steam':
            if not self.ensure_api_key('steamgriddb'):
                return
            try:
                games = services.search_games(query)
                if not games:
                    self.show_status('No games found')
                    return
                labels = [g.get('name', 'Unknown') for g in games]
                d = SelectDialog('Select Game', labels, self)
                if d.exec() != QDialog.DialogCode.Accepted or d.result_index is None:
                    return
                game = games[d.result_index]
                self.current_game_title = game.get('name')
                self.show_loading()
                self.start_worker('steam', {'game_id': game['id']}, search_id)
            except Exception as e:
                QMessageBox.critical(self, 'Error', f'SteamGridDB search failed:\n{e}')
        elif self.source == 'tmdb':
            if not self.ensure_api_key('tmdb'):
                return
            try:
                items = services.tmdb_search_multi(query)
                if not items:
                    self.show_status('No TMDB results found')
                    return
                labels = []
                for item in items:
                    label = item['title']
                    if item.get('year'):
                        label += f" ({item['media_type'].upper()}, {item['year']})"
                    labels.append(label)
                d = SelectDialog('Select Movie / TV Show', labels, self)
                if d.exec() != QDialog.DialogCode.Accepted or d.result_index is None:
                    return
                item = items[d.result_index]
                self.current_game_title = item['title'] + (f" ({item['year']})" if item.get('year') else '')
                self.show_loading()
                self.start_worker('tmdb', {'item': item}, search_id)
            except Exception as e:
                QMessageBox.critical(self, 'Error', f'TMDB search failed:\n{e}')
        elif self.source == 'system':
            self.show_loading()
            self.start_worker('system', {'query': query, 'icon_pack_dir': self.icon_pack_dir, 'search_cached': load_search_cached_logos(), 'indices': self.system_icon_indices}, search_id)

    def show_loading(self):
        self.set_placeholder('Loading images…')

    def start_worker(self, mode, payload, search_id):
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()

        payload = dict(payload)
        payload['search_id'] = search_id

        self.clear_thumbs()

        worker = Worker(mode, payload, self)
        worker.item.connect(self.add_worker_item)
        worker.done.connect(self.worker_done)
        worker.error.connect(self.worker_error)
        worker.finished.connect(lambda w=worker: self.cleanup_worker(w))

        self.worker = worker
        self.workers.append(worker)
        worker.start()


    def worker_error(self, info):
        if not self.is_current_search(info.get('search_id')):
            return
        self.show_status(info.get('message', 'Worker error'))

    def cleanup_worker(self, worker):
        if worker in self.workers:
            self.workers.remove(worker)
        if self.worker is worker:
            self.worker = None

    def worker_done(self, info):
        if not self.is_current_search(info.get('search_id')):
            return
        if self.thumb_grid.count() == 0:
            self.refresh_placeholder_text()
        if self.source == 'system' and info.get('total', 0) > info.get('count', 0):
            self.show_status(f"Showing first {info.get('count')} of {info.get('total')} matches — refine your search")
        elif info.get('count', 0) == 0:
            self.show_status('No results')

    def add_worker_item(self, item):
        if not self.is_current_search(item.get('search_id')):
            return
        try:
            if item['kind'] == 'steam':
                stored = (item['grid'], item['data'])
                self.add_steam_thumb(item['grid'], item['data'])
                self.source_state['steam']['thumbs'].append(stored)
            elif item['kind'] == 'tmdb':
                self.add_tmdb_thumb(item['data'])
                self.source_state['tmdb']['thumbs'].append(item['data'])
            elif item['kind'] == 'system':
                stored = (item['data'], item['path'])
                self.add_system_thumb(item['data'], item['path'])
                self.source_state['system']['thumbs'].append(stored)
        except Exception as e:
            self.show_status(f'Skipped unsupported image: {e}')

    def restore_thumb(self, source, item):
        try:
            if source == 'steam':
                grid, data = item
                self.add_steam_thumb(grid, data)
            elif source == 'tmdb':
                self.add_tmdb_thumb(item)
            elif source == 'system':
                data, path = item
                self.add_system_thumb(data, path)
        except Exception as e:
            self.show_status(f'Skipped unsupported image: {e}')

    def add_thumb_button(self, img, callback, context_menu=None):
        i = len(self.thumb_refs)
        btn = QPushButton()
        btn.setIcon(QIcon(pil_to_pixmap(img)))
        btn.setIconSize(QSize(img.width, img.height))
        btn.setFixedSize(img.width + 18, img.height + 18)
        btn.clicked.connect(lambda _checked=False, cb=callback: cb())
        if context_menu:
            btn.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            btn.customContextMenuRequested.connect(lambda pos, b=btn: context_menu(b.mapToGlobal(pos)))
        self.thumb_refs.append(btn)
        self.thumb_grid.addWidget(btn, (i // 3), i % 3, Qt.AlignmentFlag.AlignCenter)

    def add_steam_thumb(self, grid, data):
        img = load_image_from_bytes(data).resize((THUMB_W, THUMB_H), Image.LANCZOS)
        self.add_thumb_button(img, lambda g=grid: self.apply_steam_poster(g))

    def add_tmdb_thumb(self, data):
        img = load_image_from_bytes(data).resize((THUMB_W, THUMB_H), Image.LANCZOS)
        self.add_thumb_button(img, lambda d=data: self.apply_tmdb_poster(d))

    def add_system_thumb(self, data, path):
        img = fit_inside(load_image_from_bytes(data), ICON_THUMB_SIZE, ICON_THUMB_SIZE)
        def menu(global_pos, p=path):
            m = QMenu(self)
            if p in self.favourite_logos:
                m.addAction('★  Remove from Favourites', lambda: self.toggle_favourite_logo(p, False))
            else:
                m.addAction('☆  Add to Favourites', lambda: self.toggle_favourite_logo(p, True))
            m.exec(global_pos)
        self.add_thumb_button(img, lambda p=path: self.apply_system_icon(p), menu)

    def show_favourite_logos(self):
        self.clear_thumbs()
        valid = sorted([p for p in self.favourite_logos if os.path.isfile(p)], key=lambda p: os.path.basename(p).lower())
        if not valid:
            self.set_placeholder('No favourites yet\nRight-click any logo in search results to add one')
            return
        for path in valid:
            try:
                with open(path, 'rb') as f:
                    self.add_system_thumb(f.read(), path)
            except Exception:
                pass

    def toggle_favourite_logo(self, path, add):
        if add:
            self.favourite_logos.add(path)
            add_favourite_logo(path)
            self.show_status(f'★ Added: {os.path.basename(path)}')
        else:
            self.favourite_logos.discard(path)
            remove_favourite_logo(path)
            self.show_status(f'Removed: {os.path.basename(path)}')
        if self.source == 'favs':
            self.show_favourite_logos()

    def apply_steam_poster(self, grid):
        try:
            r = requests.get(grid['url'], timeout=15)
            r.raise_for_status()
            poster = load_image_from_bytes(r.content)
            self.selected_poster_image = poster
            self.poster_orientation = 'horizontal' if poster.width > poster.height else 'vertical'
            self.update_crop_labels()
            self.render_current()
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load poster:\n{e}')

    def apply_tmdb_poster(self, data):
        try:
            poster = load_image_from_bytes(data)
            self.selected_poster_image = poster
            self.poster_orientation = 'vertical'
            self.update_crop_labels()
            self.render_current()
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load poster:\n{e}')

    def apply_system_icon(self, path):
        try:
            self.logo_image = load_image_from_file(path)
            self.logo_path = path
            self.logo_name = sanitize_filename(os.path.splitext(os.path.basename(path))[0])
            self.render_current()
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load system logo:\n{e}')

    def ensure_api_key(self, service):
        if load_api_key(service):
            return True
        title = 'SteamGridDB API Key' if service == 'steamgriddb' else 'TMDB API Key'
        url = 'https://www.steamgriddb.com/profile/preferences/api' if service == 'steamgriddb' else 'https://www.themoviedb.org/settings/api'
        d = TextInputDialog(title, f'Enter your {title}:\n{url}', parent=self)
        if d.exec() == QDialog.DialogCode.Accepted and d.value:
            save_api_key(d.value, service)
            return True
        return False

    def open_settings(self):
        d = QDialog(self)
        d.setWindowTitle('Settings')
        d.resize(560, 720)
        layout = QVBoxLayout(d)
        layout.addWidget(QLabel('<b>Settings</b>'))
        output_label = QLabel(self.output_dir or 'No output folder set')
        output_label.setWordWrap(True)
        layout.addWidget(QLabel('<b>Output Folder</b>'))
        layout.addWidget(output_label)
        btn = QPushButton('Set / Change Output Folder')
        btn.clicked.connect(lambda: self.settings_pick_output(output_label))
        layout.addWidget(btn)
        self.add_sep(layout)
        icon_label = QLabel(self.icon_pack_dir or 'No system logo pack folder set')
        icon_label.setWordWrap(True)
        layout.addWidget(QLabel('<b>System Logo Pack Folder</b>'))
        layout.addWidget(icon_label)
        btn2 = QPushButton('Set / Change System Logo Pack Folder')
        btn2.clicked.connect(lambda: self.settings_pick_icon_pack(icon_label))
        layout.addWidget(btn2)
        self.add_sep(layout)
        cache_posters = QCheckBox('Cache poster images from URLs')
        cache_posters.setChecked(load_cache_posters())
        cache_posters.toggled.connect(save_cache_posters)
        cache_logos = QCheckBox('Cache system logo images from URLs')
        cache_logos.setChecked(load_cache_logos())
        cache_logos.toggled.connect(save_cache_logos)
        search_cached = QCheckBox('Include cached web logos in logo search')
        search_cached.setChecked(load_search_cached_logos())
        search_cached.toggled.connect(lambda v: (save_search_cached_logos(v), self.enable_logo_sources_if_needed()))
        layout.addWidget(QLabel('<b>Web Images</b>'))
        layout.addWidget(cache_posters)
        layout.addWidget(cache_logos)
        layout.addWidget(search_cached)
        self.add_sep(layout)
        for service, label in [('steamgriddb', 'SteamGridDB API Key'), ('tmdb', 'TMDB API Key')]:
            layout.addWidget(QLabel(f'<b>{label}</b>'))
            state = QLabel('Set' if load_api_key(service) else 'Not set')
            layout.addWidget(state)
            row = QHBoxLayout()
            set_btn = QPushButton('Set / Change')
            rem_btn = QPushButton('Remove')
            set_btn.clicked.connect(lambda _, s=service, st=state: self.set_api_key_from_settings(s, st))
            rem_btn.clicked.connect(lambda _, s=service, st=state: (save_api_key(None, s), st.setText('Not set'), self.show_status(f'{s} API key removed')))
            row.addWidget(set_btn)
            row.addWidget(rem_btn)
            row.addStretch(1)
            layout.addLayout(row)
        layout.addStretch(1)
        close_btn = QPushButton('Close')
        close_btn.clicked.connect(d.accept)
        layout.addWidget(close_btn)
        d.exec()

    def add_sep(self, layout):
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(line)

    def settings_pick_output(self, label):
        path = QFileDialog.getExistingDirectory(self, 'Select Output Folder')
        if path:
            self.output_dir = path
            save_output_dir(path)
            label.setText(path)
            self.update_output_folder_button()
            self.show_status('Output folder set')

    def settings_pick_icon_pack(self, label):
        path = QFileDialog.getExistingDirectory(self, 'Select System Logo Pack Folder')
        if path:
            self.icon_pack_dir = path
            save_icon_pack_dir(path)
            self.system_icon_indices.clear()
            label.setText(path)
            self.enable_logo_sources_if_needed()
            self.show_status('System logo pack folder set')

    def enable_logo_sources_if_needed(self):
        if 'system' not in self.source_buttons:
            self.rebuild_optional_source_buttons(self.controls_row)
        if self.source in self.source_buttons:
            self.source_buttons[self.source].setChecked(True)

    def set_api_key_from_settings(self, service, state_label):
        d = TextInputDialog('API Key', f'Enter {service} API key:', load_api_key(service) or '', self)
        if d.exec() == QDialog.DialogCode.Accepted and d.value:
            save_api_key(d.value, service)
            state_label.setText('Set')
            self.show_status(f'{service} API key saved')

    def load_local_poster(self):
        p, _ = QFileDialog.getOpenFileName(self, 'Select Poster', '', 'Images (*.png *.jpg *.jpeg *.webp)')
        if not p:
            return
        try:
            img = load_image_from_file(p)
            self.selected_poster_image = img
            self.poster_orientation = 'horizontal' if img.width > img.height else 'vertical'
            self.update_crop_labels()
            self.current_game_title = os.path.splitext(os.path.basename(p))[0]
            self.render_current()
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load poster:\n{e}')

    def load_logo(self):
        p, _ = QFileDialog.getOpenFileName(self, 'Select System Logo', '', 'Images (*.png *.jpg *.jpeg *.webp)')
        if not p:
            return
        try:
            self.logo_image = load_image_from_file(p)
            self.logo_path = p
            self.logo_name = sanitize_filename(os.path.splitext(os.path.basename(p))[0])
            self.render_current()
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load logo:\n{e}')

    def ask_url(self, title):
        d = TextInputDialog(title, title, parent=self)
        if d.exec() == QDialog.DialogCode.Accepted:
            return d.value
        return None

    def load_logo_from_url(self):
        url = self.ask_url('Enter System Logo URL')
        if not url:
            return
        try:
            img = load_image_from_url(url)
            self.logo_image = maybe_cache_web_image(img, url, kind='logo')
            self.logo_path = None
            self.logo_name = sanitize_filename(os.path.splitext(os.path.basename(url.split('?')[0]))[0])
            self.render_current()
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load logo:\n{e}')

    def load_poster_from_url(self):
        url = self.ask_url('Enter Poster Image URL')
        if not url:
            return
        try:
            img = load_image_from_url(url)
            self.selected_poster_image = maybe_cache_web_image(img, url, kind='poster')
            self.poster_orientation = 'horizontal' if img.width > img.height else 'vertical'
            self.update_crop_labels()
            self.current_game_title = os.path.splitext(os.path.basename(url.split('?')[0]))[0]
            self.render_current()
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to load poster:\n{e}')

    def save(self):
        if not self.output_image:
            QMessageBox.warning(self, 'No Image', 'There is no rendered image to save.')
            return
        if self.output_dir and not os.path.isdir(self.output_dir):
            try:
                os.makedirs(self.output_dir, exist_ok=True)
            except Exception:
                pass
        if not self.output_dir or not os.path.isdir(self.output_dir):
            self.settings_pick_output(QLabel())
            if not self.output_dir:
                return
        name = sanitize_filename(self.current_game_title or 'nfc_card')
        parts = [name]
        if self.logo_name:
            parts.append(self.logo_name)
        ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        path = os.path.join(self.output_dir, '_'.join(parts) + f'_{ts}.png')
        try:
            self.output_image.save(path, dpi=(300, 300))
            self.show_status('Image saved')
        except Exception as e:
            QMessageBox.critical(self, 'Error', f'Failed to save image:\n{e}')

    def save_as(self):
        if not self.output_image:
            return
        name = sanitize_filename(self.current_game_title or 'nfc_card')
        if self.logo_name:
            name += '_' + self.logo_name
        ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        default = f'{name}_{ts}.png'
        if self.output_dir:
            default = os.path.join(self.output_dir, default)
        path, _ = QFileDialog.getSaveFileName(self, 'Save Image', default, 'PNG Image (*.png)')
        if path:
            try:
                self.output_image.save(path, dpi=(300, 300))
                self.show_status('Image saved')
            except Exception as e:
                QMessageBox.critical(self, 'Error', f'Failed to save image:\n{e}')

    def open_output_dir(self):
        if not self.output_dir or not os.path.isdir(self.output_dir):
            QMessageBox.critical(self, 'Error', 'Output folder is not set or does not exist.')
            return
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.output_dir))

    def update_output_folder_button(self):
        self.open_folder_btn.setVisible(bool(self.output_dir and os.path.isdir(self.output_dir)))

    def show_status(self, text):
        self.status_label.setText(text)
        QTimer.singleShot(3000, lambda: self.status_label.setText(''))

    def open_print_pdf_window(self):
        d = QDialog(self)
        d.setWindowTitle('Print PDF Template')
        d.resize(980, 760)

        slots = [None] * 10

        layout = QVBoxLayout(d)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        content = QHBoxLayout()
        content.setSpacing(14)
        content.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addLayout(content, 1)

        # ---------------- LEFT: PREVIEW ----------------
        preview_box = QGroupBox('PDF Preview')
        preview_box.setMinimumWidth(470)
        preview_layout = QVBoxLayout(preview_box)
        preview_layout.setContentsMargins(12, 12, 12, 12)
        preview_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        preview = QLabel()
        preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        preview.setMinimumSize(420, 600)
        preview.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding
        )

        preview_layout.addWidget(
            preview,
            1,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )

        content.addWidget(
            preview_box,
            1,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )

        # ---------------- RIGHT: CARD SLOTS ----------------
        slots_box = QGroupBox('Card Slots')
        slots_box.setMinimumWidth(360)
        slots_layout = QVBoxLayout(slots_box)
        slots_layout.setContentsMargins(12, 12, 12, 12)
        slots_layout.setSpacing(6)
        slots_layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        slot_labels = []

        def update_slot_labels():
            for i, label in enumerate(slot_labels):
                loaded = slots[i] is not None
                label.setText('Loaded' if loaded else 'Empty')
                label.setStyleSheet('color: green;' if loaded else 'color: gray;')

        def update_preview():
            page = render_nfc_print_sheet(
                slots,
                show_cutlines=cutlines_check.isChecked()
            )

            pw = 390
            ph = int(page.height * (pw / page.width))

            preview.setPixmap(
                pil_to_pixmap(page.resize((pw, ph), Image.LANCZOS))
            )

            update_slot_labels()

        def load_slot(i):
            path, _ = QFileDialog.getOpenFileName(
                d,
                f'Select Card {i + 1}',
                '',
                'Images (*.png *.jpg *.jpeg *.webp)'
            )

            if not path:
                return

            try:
                slots[i] = load_image_from_file(path)
                update_preview()
            except Exception as e:
                QMessageBox.critical(
                    d,
                    'Error',
                    f'Failed to load image:\n{e}'
                )

        def clear_slot(i):
            slots[i] = None
            update_preview()

        for i in range(10):
            slot_row = QHBoxLayout()
            slot_row.setSpacing(8)

            number_label = QLabel(f'Card {i + 1}')
            number_label.setFixedWidth(55)
            number_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

            state_label = QLabel('Empty')
            state_label.setFixedWidth(62)
            state_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            state_label.setStyleSheet('color: gray;')
            slot_labels.append(state_label)

            load_btn = QPushButton('Load')
            load_btn.setFixedWidth(70)
            load_btn.clicked.connect(lambda _, idx=i: load_slot(idx))

            clear_btn = QPushButton('Clear')
            clear_btn.setFixedWidth(70)
            clear_btn.clicked.connect(lambda _, idx=i: clear_slot(idx))

            slot_row.addWidget(number_label)
            slot_row.addWidget(state_label)
            slot_row.addStretch(1)
            slot_row.addWidget(load_btn)
            slot_row.addWidget(clear_btn)

            slots_layout.addLayout(slot_row)

        slots_layout.addSpacing(8)

        def load_multiple():
            paths, _ = QFileDialog.getOpenFileNames(
                d,
                'Select Card Images',
                '',
                'Images (*.png *.jpg *.jpeg *.webp)'
            )

            if not paths:
                return

            for i in range(10):
                slots[i] = None

            for i, path in enumerate(paths[:10]):
                try:
                    slots[i] = load_image_from_file(path)
                except Exception:
                    pass

            update_preview()

        def clear_all_slots():
            for i in range(10):
                slots[i] = None
            update_preview()

        bulk_row = QHBoxLayout()
        bulk_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        load_all = QPushButton('Load Multiple')
        clear_all = QPushButton('Clear All')

        load_all.setMinimumWidth(120)
        clear_all.setMinimumWidth(100)

        load_all.clicked.connect(load_multiple)
        clear_all.clicked.connect(clear_all_slots)

        bulk_row.addWidget(load_all)
        bulk_row.addWidget(clear_all)

        slots_layout.addLayout(bulk_row)

        cutlines_check = QCheckBox('Show cutlines / borders')
        cutlines_check.setChecked(False)
        cutlines_check.toggled.connect(lambda *_: update_preview())

        cutlines_row = QHBoxLayout()
        cutlines_row.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        cutlines_row.addWidget(cutlines_check)
        slots_layout.addLayout(cutlines_row)

        slots_layout.addStretch(1)

        content.addWidget(
            slots_box,
            0,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignVCenter
        )

        # ---------------- BOTTOM BUTTONS ----------------
        bottom = QHBoxLayout()
        bottom.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addLayout(bottom)

        def export_pdf():
            if all(s is None for s in slots):
                QMessageBox.critical(
                    d,
                    'Error',
                    'Load at least one card first.'
                )
                return

            ts = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            default = (
                sanitize_filename(self.current_game_title or 'nfc_cards')
                + f'_print_sheet_{ts}.pdf'
            )
            if self.output_dir:
                default = os.path.join(self.output_dir, default)

            path, _ = QFileDialog.getSaveFileName(
                d,
                'Save Print PDF',
                default,
                'PDF File (*.pdf)'
            )

            if not path:
                return

            try:
                render_nfc_print_sheet(
                    slots,
                    show_cutlines=cutlines_check.isChecked()
                ).save(path, 'PDF', resolution=300.0)

                QMessageBox.information(
                    d,
                    'Export Complete',
                    f'Print PDF saved to:\n{path}'
                )
            except Exception as e:
                QMessageBox.critical(
                    d,
                    'Error',
                    f'Failed to create print PDF:\n{e}'
                )

        export_btn = QPushButton('Export PDF')
        close_btn = QPushButton('Close')

        export_btn.setMinimumWidth(110)
        close_btn.setMinimumWidth(90)

        export_btn.clicked.connect(export_pdf)
        close_btn.clicked.connect(d.accept)

        bottom.addWidget(export_btn)
        bottom.addWidget(close_btn)

        update_preview()
        d.exec()
