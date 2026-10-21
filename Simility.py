#!/usr/bin/env python3
"""A small PyQt6 utility for finding files with matching name prefixes."""

from __future__ import annotations

import math
import os
import shutil
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


app_version = "1.3.3"


# On some macOS installations Qt does not discover PyQt's bundled platform
# plugins from its default path. Qt reads QT_PLUGIN_PATH while its libraries
# are loaded, so relaunch before importing any PyQt modules.
if __name__ == "__main__" and sys.platform == "darwin" and not os.environ.get("SIMILITY_QT_READY"):
    qt_plugins = (
        Path(sys.prefix)
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
        / "PyQt6"
        / "Qt6"
        / "plugins"
    )
    platform_plugins = qt_plugins / "platforms"
    if platform_plugins.is_dir():
        # A fresh copy outside site-packages sidesteps a macOS/Qt discovery
        # issue observed with some virtual-environment locations.
        runtime_plugins = Path("/private/tmp") / "simility-qt-plugins"
        runtime_platforms = runtime_plugins / "platforms"
        runtime_platforms.mkdir(parents=True, exist_ok=True)
        for source_plugin in platform_plugins.glob("*.dylib"):
            target_plugin = runtime_platforms / source_plugin.name
            if (
                not target_plugin.exists()
                or target_plugin.stat().st_size != source_plugin.stat().st_size
                or target_plugin.stat().st_mtime < source_plugin.stat().st_mtime
            ):
                # Do not preserve the source timestamp: Qt's plugin cache uses
                # it, and a fresh timestamp forces metadata to be rediscovered.
                shutil.copyfile(source_plugin, target_plugin)
        launch_environment = os.environ.copy()
        existing_paths = launch_environment.get("QT_PLUGIN_PATH")
        launch_environment["QT_PLUGIN_PATH"] = (
            f"{runtime_plugins}{os.pathsep}{existing_paths}" if existing_paths else str(runtime_plugins)
        )
        launch_environment["SIMILITY_QT_READY"] = "1"
        os.execvpe(sys.executable, [sys.executable, *sys.argv], launch_environment)

from PyQt6.QtCore import QSettings, Qt
from PyQt6.QtGui import QColor, QFont, QPalette
from PyQt6.QtWidgets import (
    QApplication,
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSlider,
    QStatusBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)
from send2trash import send2trash


FILE_SIZE_ROLE = int(Qt.ItemDataRole.UserRole) + 1

FILE_TYPE_GROUPS: dict[str, tuple[str, ...]] = {
    "Apps": ("apk", "app", "dmg", "exe", "img", "iso", "pkg"),
    "Codes": (
        "bat", "c", "cmake", "conf", "cpp", "cs", "css", "dart", "ipynb",
        "java", "js", "json", "kt", "lua", "py", "r", "rs", "ruby", "sh",
        "sql", "sqlite", "swift", "ts", "xml", "yaml", "yml",
    ),
    "Compressed": ("7z", "gz", "rar", "tar", "tgz", "zip"),
    "Documents": (
        "csv", "doc", "docx", "epub", "md", "odt", "pdf", "ppt", "pptx",
        "rtf", "txt", "xls", "xlsx",
    ),
    "Music": ("aac", "aiff", "alac", "flac", "mp3", "ogg", "opus", "wav"),
    "Pictures": (
        "ai", "avif", "dng", "gif", "heic", "jpeg", "jpg", "png", "psd",
        "svg", "tiff", "webp",
    ),
    "Videos": ("avi", "hevc", "mkv", "mov", "mp4", "ts", "webm"),
}
ALL_FILE_TYPES = frozenset(
    extension for extensions in FILE_TYPE_GROUPS.values() for extension in extensions
)


@dataclass(frozen=True)
class FileEntry:
    """A file displayed in a result group."""

    path: Path
    prefix: str


def matching_prefix(name: str, percentage: int) -> str:
    """Return the leading percentage of a filename stem, case-insensitively.

    A one-character prefix is used for non-empty stems so that a low percentage
    still produces useful, deterministic results.
    """

    stem = Path(name).stem.strip()
    if not stem:
        stem = name.strip()
    if not stem:
        return ""
    character_count = max(1, math.ceil(len(stem) * percentage / 100))
    return stem[:character_count].casefold()


def comparison_name(name: str, simplify: bool = False) -> str:
    """Return the filename stem used for similarity comparisons only."""

    stem = Path(name).stem.strip() or name.strip()
    if simplify:
        stem = stem.translate(str.maketrans("-_+.", "    "))
    return stem.casefold()


def normalize_file_extensions(text: str) -> set[str]:
    """Return lowercase, dot-free extensions entered in the custom field."""

    return {
        extension.strip().lstrip(".").casefold()
        for extension in text.split()
        if extension.strip().lstrip(".")
    }


def find_similar_files(
    folder: Path,
    percentage: int,
    include_subfolders: bool = True,
    simplify_names: bool = False,
    included_file_types: set[str] | None = None,
) -> dict[str, list[FileEntry]]:
    """Group files whose common start meets the requested percentage.

    Names can have different lengths: ``Report_one`` and ``Report_three`` are
    still grouped at 30% because their shared beginning is at least 30% of
    each stem. Matching pairs are collected into connected groups. The search
    can include subfolders or be limited to the selected folder itself. When
    requested, dashes, underscores, periods, and plus signs are treated as
    spaces for matching while displayed filenames remain unchanged. When a
    type filter is provided, only files with one of the included extensions
    are considered.
    """

    candidates: list[tuple[Path, str]] = []
    if include_subfolders:
        paths = (Path(root) / filename for root, _, files in os.walk(folder) for filename in files)
    else:
        paths = (path for path in folder.iterdir() if path.is_file())
    for path in paths:
        if path.name == ".DS_Store":
            continue
        if included_file_types is not None:
            extension = path.suffix.lstrip(".").casefold()
            if extension not in included_file_types:
                continue
        stem = comparison_name(path.name, simplify_names)
        if stem:
            candidates.append((path, stem))

    parent = list(range(len(candidates)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(first: int, second: int) -> None:
        first_root, second_root = find(first), find(second)
        if first_root != second_root:
            parent[second_root] = first_root

    def common_start(first: str, second: str) -> str:
        length = 0
        limit = min(len(first), len(second))
        while length < limit and first[length] == second[length]:
            length += 1
        return first[:length]

    for first in range(len(candidates)):
        for second in range(first + 1, len(candidates)):
            first_name, second_name = candidates[first][1], candidates[second][1]
            shared = common_start(first_name, second_name)
            if len(shared) >= max(1, math.ceil(len(first_name) * percentage / 100)) and len(shared) >= max(1, math.ceil(len(second_name) * percentage / 100)):
                union(first, second)

    components: dict[int, list[tuple[Path, str]]] = defaultdict(list)
    for index, candidate in enumerate(candidates):
        components[find(index)].append(candidate)

    groups: dict[str, list[FileEntry]] = {}
    for component in components.values():
        if len(component) < 2:
            continue
        shared = component[0][1]
        for _, stem in component[1:]:
            shared = common_start(shared, stem)
        # Include a representative filename only when two disjoint components
        # happen to share the same common text.
        label = shared or component[0][1]
        if label in groups:
            label = f"{label} ({component[0][0].name})"
        groups[label] = [FileEntry(path=path, prefix=label) for path, _ in component]
    return groups


class Simility(QMainWindow):
    def __init__(self, settings: QSettings | None = None) -> None:
        super().__init__()
        self.settings = settings if settings is not None else QSettings(
            "Simility", "Simility"
        )
        self.selected_folder: Path | None = None
        self.selected_file_types: set[str] = set(ALL_FILE_TYPES)
        self.custom_file_types: set[str] = set()
        self.setWindowTitle("Simility")
        self.setMinimumSize(820, 580)
        self._build_interface()
        self._restore_settings()

    def _build_interface(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(24, 24, 24, 20)
        layout.setSpacing(14)

        title_row = QHBoxLayout()
        title = QLabel("Simility")
        title.setObjectName("title")
        self.theme_button = QPushButton()
        self.theme_button.setObjectName("themeButton")
        self.theme_button.setFixedSize(38, 38)
        self.theme_button.clicked.connect(self._toggle_theme)
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.theme_button)
        subtitle = QLabel(
            "Choose a folder to group files whose names begin with the same text. "
            "Select files you no longer need, then clean them up."
        )
        subtitle.setWordWrap(True)
        layout.addLayout(title_row)
        layout.addWidget(subtitle)

        folder_row = QHBoxLayout()
        self.folder_label = QLabel("No folder selected")
        self.folder_label.setObjectName("folderLabel")
        self.folder_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        choose_button = QPushButton("Choose Folder…")
        choose_button.clicked.connect(self.choose_folder)
        folder_row.addWidget(self.folder_label, 1)
        folder_row.addWidget(choose_button)
        layout.addLayout(folder_row)

        controls = QFrame()
        controls.setObjectName("controls")
        controls_layout = QVBoxLayout(controls)
        controls_layout.setContentsMargins(14, 10, 14, 10)
        similarity_row = QHBoxLayout()
        similarity_row.addWidget(QLabel("Name prefix similarity:"))
        self.similarity_slider = QSlider(Qt.Orientation.Horizontal)
        self.similarity_slider.setRange(1, 100)
        self.similarity_slider.setValue(30)
        self.similarity_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.similarity_slider.setTickInterval(10)
        self.similarity_slider.valueChanged.connect(self._update_similarity_label)
        similarity_row.addWidget(self.similarity_slider, 1)
        self.similarity_label = QLabel("30%")
        self.similarity_label.setMinimumWidth(42)
        similarity_row.addWidget(self.similarity_label)
        self.search_button = QPushButton("Search Files")
        self.search_button.setObjectName("primaryButton")
        self.search_button.clicked.connect(self.search_files)
        similarity_row.addWidget(self.search_button)
        controls_layout.addLayout(similarity_row)
        self.include_subfolders_checkbox = QCheckBox("Include Sub Folders")
        self.include_subfolders_checkbox.setChecked(True)
        controls_layout.addWidget(self.include_subfolders_checkbox)
        self.simplify_file_names_checkbox = QCheckBox(
            "Simplify file names before checking for similarity"
        )
        controls_layout.addWidget(self.simplify_file_names_checkbox)
        self.file_type_selector_button = QPushButton("Select File Types")
        self.file_type_selector_button.clicked.connect(self.select_file_types)
        controls_layout.addWidget(self.file_type_selector_button)
        layout.addWidget(controls)

        self.summary_label = QLabel("Select a folder, then search for matching file names.")
        layout.addWidget(self.summary_label)

        self.results = QTreeWidget()
        self.results.setColumnCount(4)
        self.results.setHeaderLabels(["File", "Location", "Size", "Date Modified"])
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.results.setAlternatingRowColors(True)
        header = self.results.header()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(False)
        header.setMinimumSectionSize(80)
        for column, width in enumerate((270, 390, 100, 165)):
            header.resizeSection(column, width)
        self.results.itemChanged.connect(self._group_checkbox_changed)
        layout.addWidget(self.results, 1)

        bottom_row = QHBoxLayout()
        self.select_all_button = QPushButton("Select All Results")
        self.select_all_button.clicked.connect(lambda: self._set_all_checks(Qt.CheckState.Checked))
        self.select_older_button = QPushButton("Select All Older Files")
        self.select_older_button.clicked.connect(self._select_older_files)
        self.reverse_selection_button = QPushButton("Reverse Selection")
        self.reverse_selection_button.clicked.connect(self._reverse_selection)
        self.clear_selection_button = QPushButton("Clear Selection")
        self.clear_selection_button.clicked.connect(lambda: self._set_all_checks(Qt.CheckState.Unchecked))
        self.move_to_folder_button = QPushButton("Move to Another Folder")
        self.move_to_folder_button.clicked.connect(self.move_selected_to_another_folder)
        self.clean_button = QPushButton("Move to Trash")
        self.clean_button.setObjectName("dangerButton")
        self.clean_button.clicked.connect(self.clean_selected)
        bottom_row.addWidget(self.select_all_button)
        bottom_row.addWidget(self.select_older_button)
        bottom_row.addWidget(self.reverse_selection_button)
        bottom_row.addWidget(self.clear_selection_button)
        bottom_row.addStretch()
        bottom_row.addWidget(self.move_to_folder_button)
        bottom_row.addWidget(self.clean_button)
        layout.addLayout(bottom_row)

        status_bar = QStatusBar()
        self.setStatusBar(status_bar)
        self.version_label = QLabel(f"V{app_version}")
        self.version_label.setObjectName("versionLabel")
        status_bar.addPermanentWidget(self.version_label)
        self._apply_theme("light")

    def _update_similarity_label(self, value: int) -> None:
        self.similarity_label.setText(f"{value}%")

    def _toggle_theme(self) -> None:
        self._apply_theme("dark" if self.theme == "light" else "light")

    def _apply_theme(self, theme: str) -> None:
        """Apply a complete, readable light or dark appearance."""

        self.theme = "dark" if theme == "dark" else "light"
        is_dark = self.theme == "dark"
        colors = (
            {
                "window": "#161b22", "text": "#e8edf4", "base": "#202833",
                "alternate": "#26313d", "button": "#283442", "border": "#3d4a59",
                "hover": "#334152", "header": "#111820", "header_border": "#435060",
                "muted": "#aeb9c7", "slider": "#586678", "folder": "#202833",
                "checkbox_border": "#aeb9c7",
            }
            if is_dark
            else {
                "window": "#f7f7fa", "text": "#202124", "base": "#ffffff",
                "alternate": "#f5f7fa", "button": "#ffffff", "border": "#d6d8df",
                "hover": "#f0f2f5", "header": "#25272b", "header_border": "#4b4e54",
                "muted": "#4d515a", "slider": "#c9cdd5", "folder": "#ffffff",
                "checkbox_border": "#202124",
            }
        )
        app = QApplication.instance()
        if app is not None:
            palette = QPalette()
            palette.setColor(QPalette.ColorRole.Window, QColor(colors["window"]))
            palette.setColor(QPalette.ColorRole.WindowText, QColor(colors["text"]))
            palette.setColor(QPalette.ColorRole.Base, QColor(colors["base"]))
            palette.setColor(QPalette.ColorRole.AlternateBase, QColor(colors["alternate"]))
            palette.setColor(QPalette.ColorRole.Text, QColor(colors["text"]))
            palette.setColor(QPalette.ColorRole.Button, QColor(colors["button"]))
            palette.setColor(QPalette.ColorRole.ButtonText, QColor(colors["text"]))
            palette.setColor(QPalette.ColorRole.Highlight, QColor("#3b82f6"))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
            app.setPalette(palette)

        icon = "☾" if is_dark else "☀"
        next_theme = "Light" if is_dark else "Dark"
        self.theme_button.setText(icon)
        self.theme_button.setToolTip(
            f"{self.theme.title()} appearance active. Switch to {next_theme} appearance."
        )
        self.theme_button.setAccessibleName(f"Switch to {next_theme} appearance")
        self.setStyleSheet(
            f"QWidget {{ color: {colors['text']}; }}"
            f"QMainWindow {{ background: {colors['window']}; }}"
            f"QLabel#title {{ font-size: 28px; font-weight: 700; color: {colors['text']}; }}"
            f"QLabel#folderLabel {{ color: {colors['text']}; padding: 8px 10px; background: {colors['folder']}; border: 1px solid {colors['border']}; border-radius: 6px; }}"
            f"QLabel#versionLabel {{ color: {colors['muted']}; padding-right: 4px; }}"
            f"QFrame#controls {{ background: {colors['base']}; border: 1px solid {colors['border']}; border-radius: 8px; }}"
            f"QPushButton {{ color: {colors['text']}; background: {colors['button']}; border: 1px solid {colors['border']}; border-radius: 5px; padding: 7px 12px; }}"
            f"QPushButton:hover {{ background: {colors['hover']}; }}"
            f"QPushButton#themeButton {{ font-size: 20px; padding: 0; border-radius: 19px; }}"
            "QPushButton#primaryButton { background: #2369c8; color: white; font-weight: 600; border: none; border-radius: 5px; }"
            "QPushButton#dangerButton { background: #c23934; color: white; font-weight: 600; border: none; border-radius: 5px; }"
            f"QTreeWidget {{ color: {colors['text']}; background: {colors['base']}; border: 1px solid {colors['border']}; border-radius: 6px; }}"
            f"QTreeWidget::item {{ color: {colors['text']}; }}"
            f"QTreeWidget::item:alternate {{ background: {colors['alternate']}; }}"
            f"QCheckBox::indicator:unchecked, QTreeWidget::indicator:unchecked {{ background: {colors['base']}; border: 1px solid {colors['checkbox_border']}; }}"
            f"QHeaderView::section {{ color: white; background: {colors['header']}; padding: 6px; border: 1px solid {colors['header_border']}; font-weight: 600; }}"
            f"QSlider::groove:horizontal {{ background: {colors['slider']}; height: 6px; border-radius: 3px; }}"
            "QSlider::handle:horizontal { background: #3b82f6; width: 18px; margin: -6px 0; border-radius: 9px; }"
            f"QStatusBar {{ color: {colors['muted']}; background: {colors['window']}; }}"
        )

    def _restore_settings(self) -> None:
        """Restore non-destructive interface preferences from the last session."""

        percentage = self.settings.value("matching/percentage", 30, type=int)
        self.similarity_slider.setValue(max(1, min(100, percentage)))
        self.include_subfolders_checkbox.setChecked(
            self.settings.value("matching/include_subfolders", True, type=bool)
        )
        self.simplify_file_names_checkbox.setChecked(
            self.settings.value("matching/simplify_file_names", False, type=bool)
        )
        saved_file_types = self.settings.value("matching/file_types", None)
        if saved_file_types is None:
            self.selected_file_types = set(ALL_FILE_TYPES)
        elif isinstance(saved_file_types, str):
            self.selected_file_types = normalize_file_extensions(saved_file_types)
        else:
            self.selected_file_types = {
                str(extension).strip().lstrip(".").casefold()
                for extension in saved_file_types
                if str(extension).strip().lstrip(".")
            }
        self.selected_file_types.intersection_update(ALL_FILE_TYPES)
        self.custom_file_types = normalize_file_extensions(
            self.settings.value("matching/custom_file_types", "", type=str)
        )
        self._apply_theme(self.settings.value("appearance/theme", "light", type=str))

        width = self.settings.value("window/width", 1100, type=int)
        height = self.settings.value("window/height", 760, type=int)
        self.resize(max(self.minimumWidth(), width), max(self.minimumHeight(), height))

        header = self.results.header()
        for column in range(self.results.columnCount()):
            saved_width = self.settings.value(f"columns/{column}", type=int)
            if saved_width is not None and saved_width >= header.minimumSectionSize():
                header.resizeSection(column, saved_width)

        saved_folder = self.settings.value("matching/folder", "", type=str)
        if saved_folder:
            folder = Path(saved_folder)
            if folder.is_dir():
                self.selected_folder = folder
                self.folder_label.setText(str(folder))
                self.statusBar().showMessage("Last selected folder restored. Click Search Files to scan it.")
                return
        self.statusBar().showMessage("Select a folder to start the analyze.")

    def _save_settings(self) -> None:
        self.settings.setValue("matching/percentage", self.similarity_slider.value())
        self.settings.setValue("matching/include_subfolders", self.include_subfolders_checkbox.isChecked())
        self.settings.setValue(
            "matching/simplify_file_names",
            self.simplify_file_names_checkbox.isChecked(),
        )
        self.settings.setValue("matching/file_types", sorted(self.selected_file_types))
        self.settings.setValue(
            "matching/custom_file_types", " ".join(sorted(self.custom_file_types))
        )
        self.settings.setValue("appearance/theme", self.theme)
        self.settings.setValue(
            "matching/folder", str(self.selected_folder) if self.selected_folder else ""
        )
        self.settings.setValue("window/width", self.width())
        self.settings.setValue("window/height", self.height())
        header = self.results.header()
        for column in range(self.results.columnCount()):
            self.settings.setValue(f"columns/{column}", header.sectionSize(column))
        self.settings.sync()

    def closeEvent(self, event) -> None:
        self._save_settings()
        super().closeEvent(event)

    def choose_folder(self) -> None:
        start_at = str(self.selected_folder) if self.selected_folder else str(Path.home())
        selected = QFileDialog.getExistingDirectory(self, "Choose a folder", start_at)
        if selected:
            self.selected_folder = Path(selected)
            self.folder_label.setText(str(self.selected_folder))
            self.statusBar().showMessage("Folder selected. Choose a percentage and search.")

    def select_file_types(self) -> None:
        """Open the modal selector for built-in and custom file extensions."""

        dialog = QDialog(self)
        dialog.setWindowTitle("Select File Types")
        dialog.setModal(True)
        dialog.resize(540, 620)
        layout = QVBoxLayout(dialog)

        selector = QTreeWidget()
        selector.setColumnCount(1)
        selector.setHeaderLabels(["File Type Selector"])
        selector.setAlternatingRowColors(True)
        selector.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        selector.blockSignals(True)
        for group_name in sorted(FILE_TYPE_GROUPS):
            group = QTreeWidgetItem([group_name])
            group.setFlags(
                group.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsAutoTristate
            )
            selector.addTopLevelItem(group)
            for extension in sorted(FILE_TYPE_GROUPS[group_name]):
                item = QTreeWidgetItem([f".{extension}"])
                item.setData(0, Qt.ItemDataRole.UserRole, extension)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(
                    0,
                    Qt.CheckState.Checked
                    if extension in self.selected_file_types
                    else Qt.CheckState.Unchecked,
                )
                group.addChild(item)
            selected_count = sum(
                extension in self.selected_file_types
                for extension in FILE_TYPE_GROUPS[group_name]
            )
            group.setCheckState(
                0,
                Qt.CheckState.Checked
                if selected_count == group.childCount()
                else (
                    Qt.CheckState.PartiallyChecked
                    if selected_count
                    else Qt.CheckState.Unchecked
                ),
            )
            group.setExpanded(True)
        selector.blockSignals(False)
        layout.addWidget(selector, 1)

        def update_group_state(group: QTreeWidgetItem) -> None:
            checked_count = sum(
                group.child(index).checkState(0) == Qt.CheckState.Checked
                for index in range(group.childCount())
            )
            group.setCheckState(
                0,
                Qt.CheckState.Checked
                if checked_count == group.childCount()
                else (
                    Qt.CheckState.PartiallyChecked
                    if checked_count
                    else Qt.CheckState.Unchecked
                ),
            )

        def sync_group_selection(item: QTreeWidgetItem, _: int) -> None:
            if item.parent() is not None:
                selector.blockSignals(True)
                update_group_state(item.parent())
                selector.blockSignals(False)
                return

            state = item.checkState(0)
            if state == Qt.CheckState.PartiallyChecked:
                return
            selector.blockSignals(True)
            for index in range(item.childCount()):
                item.child(index).setCheckState(0, state)
            selector.blockSignals(False)

        selector.itemChanged.connect(sync_group_selection)

        custom_label = QLabel("Custom File Types")
        layout.addWidget(custom_label)
        custom_input = QLineEdit(" ".join(sorted(self.custom_file_types)))
        custom_input.setPlaceholderText("Example: dng zfs pkg")
        layout.addWidget(custom_input)

        button_row = QHBoxLayout()
        select_all_button = QPushButton("Select All")
        reverse_button = QPushButton("Reverse Selection")
        clear_button = QPushButton("Clear Selection")

        def set_all(state: Qt.CheckState) -> None:
            selector.blockSignals(True)
            for row in range(selector.topLevelItemCount()):
                group = selector.topLevelItem(row)
                for index in range(group.childCount()):
                    group.child(index).setCheckState(0, state)
                group.setCheckState(0, state)
            selector.blockSignals(False)

        def reverse_selection() -> None:
            selector.blockSignals(True)
            for row in range(selector.topLevelItemCount()):
                group = selector.topLevelItem(row)
                for index in range(group.childCount()):
                    item = group.child(index)
                    item.setCheckState(
                        0,
                        Qt.CheckState.Unchecked
                        if item.checkState(0) == Qt.CheckState.Checked
                        else Qt.CheckState.Checked,
                    )
                update_group_state(group)
            selector.blockSignals(False)

        select_all_button.clicked.connect(lambda: set_all(Qt.CheckState.Checked))
        reverse_button.clicked.connect(reverse_selection)
        clear_button.clicked.connect(lambda: set_all(Qt.CheckState.Unchecked))
        button_row.addWidget(select_all_button)
        button_row.addWidget(reverse_button)
        button_row.addWidget(clear_button)
        button_row.addStretch()
        cancel_button = QPushButton("Cancel")
        done_button = QPushButton("Done")
        done_button.setObjectName("primaryButton")
        cancel_button.clicked.connect(dialog.reject)
        done_button.clicked.connect(dialog.accept)
        button_row.addWidget(cancel_button)
        button_row.addWidget(done_button)
        layout.addLayout(button_row)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.selected_file_types = {
            str(group.child(index).data(0, Qt.ItemDataRole.UserRole))
            for row in range(selector.topLevelItemCount())
            for group in [selector.topLevelItem(row)]
            for index in range(group.childCount())
            if group.child(index).checkState(0) == Qt.CheckState.Checked
        }
        self.custom_file_types = normalize_file_extensions(custom_input.text())
        self.settings.setValue("matching/file_types", sorted(self.selected_file_types))
        self.settings.setValue(
            "matching/custom_file_types", " ".join(sorted(self.custom_file_types))
        )
        self.settings.sync()

    def search_files(self) -> None:
        if self.selected_folder is None:
            QMessageBox.information(self, "Choose a folder", "Please choose a folder before searching.")
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        self.search_button.setEnabled(False)
        try:
            groups = find_similar_files(
                self.selected_folder,
                self.similarity_slider.value(),
                self.include_subfolders_checkbox.isChecked(),
                self.simplify_file_names_checkbox.isChecked(),
                self.selected_file_types | self.custom_file_types,
            )
            self._show_results(groups)
        except OSError as error:
            QMessageBox.warning(self, "Search could not finish", f"Some files could not be read.\n\n{error}")
        finally:
            self.search_button.setEnabled(True)
            QApplication.restoreOverrideCursor()

    def _show_results(self, groups: dict[str, list[FileEntry]]) -> None:
        self.results.blockSignals(True)
        self.results.clear()
        file_count = 0
        for prefix, entries in sorted(groups.items(), key=lambda item: item[0]):
            group = QTreeWidgetItem([f'“{prefix}” — {len(entries)} matching files', "", "", ""])
            group.setData(0, Qt.ItemDataRole.UserRole, prefix)
            title_font = QFont(group.font(0))
            title_font.setBold(True)
            group.setFont(0, title_font)
            group.setFlags(group.flags() | Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsAutoTristate)
            group.setCheckState(0, Qt.CheckState.Unchecked)
            self.results.addTopLevelItem(group)
            group.setExpanded(True)
            files_with_details: list[tuple[FileEntry, str, str, float, int]] = []
            for entry in entries:
                try:
                    details = entry.path.stat()
                    size_text = self._format_size(details.st_size)
                    modified_text = self._format_modified_date(details.st_mtime)
                    modified_timestamp = details.st_mtime
                    size_bytes = details.st_size
                except OSError:
                    size_text = "Unavailable"
                    modified_text = "Unavailable"
                    modified_timestamp = float("-inf")
                    size_bytes = 0
                files_with_details.append(
                    (entry, size_text, modified_text, modified_timestamp, size_bytes)
                )

            # Newest files appear first, with the path providing a stable
            # secondary order for files modified at the same instant.
            for entry, size_text, modified_text, _, size_bytes in sorted(
                files_with_details,
                key=lambda file: (file[3], str(file[0].path).casefold()),
                reverse=True,
            ):
                item = QTreeWidgetItem(
                    [entry.path.name, str(entry.path.parent), size_text, modified_text]
                )
                item.setData(0, Qt.ItemDataRole.UserRole, str(entry.path))
                item.setData(0, FILE_SIZE_ROLE, size_bytes)
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(0, Qt.CheckState.Unchecked)
                group.addChild(item)
                file_count += 1
            self._update_group_title(group)
        self.results.blockSignals(False)
        percentage = self.similarity_slider.value()
        if groups:
            self.summary_label.setText(f"Found {len(groups)} matching groups containing {file_count} files at {percentage}% similarity.")
            self.statusBar().showMessage("Select individual files or an entire group.")
        else:
            self.summary_label.setText(f"No matching file-name groups found at {percentage}% similarity.")
            self.statusBar().showMessage("Try lowering the similarity percentage.")

    def _group_checkbox_changed(self, item: QTreeWidgetItem, _: int) -> None:
        # Qt propagates checks automatically with ItemIsAutoTristate; refresh
        # the affected summaries after the final child state is applied.
        self._refresh_group_titles()
        self._show_selection_summary()

    def _refresh_group_titles(self) -> None:
        """Update every group header with the total size of checked files."""

        self.results.blockSignals(True)
        try:
            for row in range(self.results.topLevelItemCount()):
                self._update_group_title(self.results.topLevelItem(row))
        finally:
            self.results.blockSignals(False)

    def _update_group_title(self, group: QTreeWidgetItem) -> None:
        """Set a group's title while retaining its original matched prefix."""

        prefix = group.data(0, Qt.ItemDataRole.UserRole)
        selected_items = [
            group.child(index)
            for index in range(group.childCount())
            if group.child(index).checkState(0) == Qt.CheckState.Checked
        ]
        title = f'“{prefix}” — {group.childCount()} matching files'
        if selected_items:
            selected_size = sum(
                int(item.data(0, FILE_SIZE_ROLE) or 0) for item in selected_items
            )
            title += f" (Selected size: {self._format_size(selected_size)})"
        group.setText(0, title)

    def _set_all_checks(self, state: Qt.CheckState) -> None:
        self.results.blockSignals(True)
        for row in range(self.results.topLevelItemCount()):
            self.results.topLevelItem(row).setCheckState(0, state)
        self.results.blockSignals(False)
        self._refresh_group_titles()
        self._show_selection_summary()

    def _select_older_files(self) -> None:
        """Select every file except the newest one in each matching group."""

        self.results.blockSignals(True)
        for row in range(self.results.topLevelItemCount()):
            group = self.results.topLevelItem(row)
            file_items = [group.child(index) for index in range(group.childCount())]
            if not file_items:
                continue
            newest_item = max(file_items, key=self._item_modified_timestamp)
            for item in file_items:
                state = (
                    Qt.CheckState.Unchecked
                    if item is newest_item
                    else Qt.CheckState.Checked
                )
                item.setCheckState(0, state)
        self.results.blockSignals(False)
        self._refresh_group_titles()
        self._show_selection_summary()

    def _reverse_selection(self) -> None:
        """Invert the selected state of every file currently shown."""

        self.results.blockSignals(True)
        for row in range(self.results.topLevelItemCount()):
            group = self.results.topLevelItem(row)
            for index in range(group.childCount()):
                item = group.child(index)
                state = (
                    Qt.CheckState.Unchecked
                    if item.checkState(0) == Qt.CheckState.Checked
                    else Qt.CheckState.Checked
                )
                item.setCheckState(0, state)
        self.results.blockSignals(False)
        self._refresh_group_titles()
        self._show_selection_summary()

    def _show_selection_summary(self) -> None:
        """Show the selected file count and aggregate byte size in the footer."""

        selected_count = 0
        selected_size = 0
        for row in range(self.results.topLevelItemCount()):
            group = self.results.topLevelItem(row)
            for index in range(group.childCount()):
                item = group.child(index)
                if item.checkState(0) == Qt.CheckState.Checked:
                    selected_count += 1
                    selected_size += int(item.data(0, FILE_SIZE_ROLE) or 0)
        self.statusBar().showMessage(
            f"{selected_count} file(s) selected for cleanup. "
            f"Selected files size: {self._format_size(selected_size)}."
        )

    @staticmethod
    def _item_modified_timestamp(item: QTreeWidgetItem) -> float:
        try:
            path = Path(item.data(0, Qt.ItemDataRole.UserRole))
            return path.stat().st_mtime
        except (OSError, TypeError):
            return float("-inf")

    def _checked_file_paths(self) -> list[Path]:
        selected: list[Path] = []
        for row in range(self.results.topLevelItemCount()):
            group = self.results.topLevelItem(row)
            for index in range(group.childCount()):
                item = group.child(index)
                if item.checkState(0) == Qt.CheckState.Checked:
                    selected.append(Path(item.data(0, Qt.ItemDataRole.UserRole)))
        return selected

    def move_selected_to_another_folder(self) -> None:
        selected = self._checked_file_paths()
        if not selected:
            QMessageBox.information(self, "Nothing selected", "Select one or more files to move.")
            return

        destination = QFileDialog.getExistingDirectory(
            self, "Choose destination folder", str(selected[0].parent)
        )
        if not destination:
            return

        target_folder = Path(destination)
        prompt = QMessageBox(self)
        prompt.setIcon(QMessageBox.Icon.Question)
        prompt.setWindowTitle("Move selected files?")
        prompt.setText(f"Move {len(selected)} selected file(s) to this folder?")
        prompt.setInformativeText(str(target_folder))
        prompt.addButton(QMessageBox.StandardButton.Cancel)
        move_button = prompt.addButton("Move Files", QMessageBox.ButtonRole.AcceptRole)
        prompt.setDefaultButton(QMessageBox.StandardButton.Cancel)
        prompt.exec()
        if prompt.clickedButton() is not move_button:
            return

        moved, failures = self._move_files_to_folder(selected, target_folder)
        self.search_files()
        self._show_move_result(moved, failures, target_folder)

    @staticmethod
    def _move_files_to_folder(
        selected: list[Path], destination: Path
    ) -> tuple[int, list[str]]:
        """Move files without overwriting a destination file of the same name."""

        moved, failures = 0, []
        for path in selected:
            target = destination / path.name
            try:
                if path.parent.resolve() == destination.resolve():
                    raise OSError("The file is already in the selected destination folder")
                if target.exists():
                    raise FileExistsError("A file with this name already exists in the destination folder")
                shutil.move(str(path), str(destination))
                moved += 1
            except (OSError, shutil.Error) as error:
                failures.append(f"{path.name}: {error}")
        return moved, failures

    def _show_move_result(
        self, moved: int, failures: list[str], destination: Path
    ) -> None:
        message = f"Moved {moved} file(s) to:\n{destination}"
        if failures:
            message += "\n\nCould not move:\n" + "\n".join(failures[:8])
            if len(failures) > 8:
                message += f"\n…and {len(failures) - 8} more."
            QMessageBox.warning(self, "Move completed with issues", message)
        else:
            QMessageBox.information(self, "Move complete", message)

    def clean_selected(self) -> None:
        selected = self._checked_file_paths()
        if not selected:
            QMessageBox.information(self, "Nothing selected", "Select one or more files to clean up.")
            return

        prompt = QMessageBox(self)
        prompt.setIcon(QMessageBox.Icon.Warning)
        prompt.setWindowTitle("Move selected files to Trash?")
        prompt.setText(f"Move {len(selected)} selected file(s) to the Trash?")
        prompt.setInformativeText("You can restore the files from the Trash later if needed.")
        prompt.addButton(QMessageBox.StandardButton.Cancel)
        delete_button = prompt.addButton(
            "Move to Trash", QMessageBox.ButtonRole.DestructiveRole
        )
        prompt.setDefaultButton(QMessageBox.StandardButton.Cancel)
        prompt.exec()
        if prompt.clickedButton() is not delete_button:
            return

        deleted, failures = 0, []
        for path in selected:
            try:
                send2trash(str(path))
                deleted += 1
            except OSError as error:
                failures.append(f"{path.name}: {error}")

        # Refresh against the same folder so the results always reflect disk state.
        self.search_files()
        message = f"Moved {deleted} file(s) to the Trash."
        if failures:
            message += "\n\nCould not move to Trash:\n" + "\n".join(failures[:8])
            if len(failures) > 8:
                message += f"\n…and {len(failures) - 8} more."
            QMessageBox.warning(self, "Move to Trash completed with issues", message)
        else:
            QMessageBox.information(self, "Move to Trash complete", message)

    @staticmethod
    def _format_size(size: int) -> str:
        for unit in ("B", "KB", "MB", "GB", "TB"):
            if size < 1024 or unit == "TB":
                return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    @staticmethod
    def _format_modified_date(timestamp: float) -> str:
        return datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M")


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Simility")
    # Use a light palette so macOS dark appearance cannot make content text
    # white while the application uses light backgrounds.
    app.setStyle("Fusion")
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#f7f7fa"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#202124"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#f5f7fa"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#202124"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#202124"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2369c8"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    app.setPalette(palette)
    window = Simility()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
