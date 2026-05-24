from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QFileDialog, QFrame, QGridLayout, QGroupBox, QHBoxLayout, QLabel,
    QLineEdit, QListWidget, QListWidgetItem, QMainWindow, QMessageBox,
    QPlainTextEdit, QProgressBar, QPushButton, QSizePolicy, QStackedWidget,
    QVBoxLayout, QWidget,
)

from .. import APP_NAME, APP_VERSION
from ..paths import project_dir as make_project_dir, safe_slug
from ..station import (
    StationMeta, Song, install_logo, make_placeholder_logo, save_meta,
)
from .workers import BuildWorker


MODES = [
    ("spotify", "Spotify Radio",
     "Paste a public Spotify playlist URL. Tracks are matched on YouTube and downloaded.",
     "Spotify playlist URL"),
    ("youtube", "YouTube Radio",
     "Paste a YouTube playlist or video URL. Audio is downloaded directly.",
     "YouTube playlist or video URL"),
    ("custom",  "Custom Station",
     "Pick your own local audio files (mp3, wav, flac, m4a, opus, ...).",
     None),
]


class ModeCard(QFrame):
    def __init__(self, key: str, title: str, subtitle: str, on_click):
        super().__init__()
        self.setObjectName("ModeCard")
        self.setProperty("selected", False)
        self.key = key
        self.setCursor(Qt.PointingHandCursor)
        layout = QVBoxLayout(self)
        layout.setSpacing(6)
        t = QLabel(title); t.setObjectName("ModeTitle")
        s = QLabel(subtitle); s.setObjectName("ModeSubtitle"); s.setWordWrap(True)
        layout.addWidget(t)
        layout.addWidget(s)
        layout.addStretch(1)
        self._on_click = on_click

    def mousePressEvent(self, ev):
        self._on_click(self.key)
        super().mousePressEvent(ev)

    def set_selected(self, on: bool):
        self.setProperty("selected", "true" if on else "false")
        # Re-polish so the dynamic property selector takes effect.
        self.style().unpolish(self); self.style().polish(self)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{APP_NAME} v{APP_VERSION}")
        self.resize(1100, 720)
        self.setMinimumSize(900, 600)

        self._mode: Optional[str] = None
        self._files: list[Path] = []
        self._logo_src: Optional[Path] = None
        self._fh6_tool_path: Optional[Path] = None

        self._task_thread: Optional[QThread] = None
        self._task_worker: Optional[BuildWorker] = None

        self.stack = QStackedWidget()
        self.setCentralWidget(self.stack)

        self.page_mode = self._build_mode_page()
        self.page_config = self._build_config_page()
        self.page_build = self._build_build_page()
        self.page_done = self._build_done_page()

        for p in (self.page_mode, self.page_config, self.page_build, self.page_done):
            self.stack.addWidget(p)
        self.stack.setCurrentWidget(self.page_mode)

    # ---------- Page 1: mode select ----------

    def _build_mode_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        title = QLabel("Choose a radio source")
        title.setObjectName("StepTitle")
        v.addWidget(title)
        hint = QLabel(
            "Forza Horizon Radio Maker builds a custom radio station you can apply "
            "to Forza Horizon 6 via the FH6 Radio Tool. Pick where your songs come from."
        )
        hint.setObjectName("CompactHint")
        hint.setWordWrap(True)
        v.addWidget(hint)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(12)
        self._cards: dict[str, ModeCard] = {}
        for key, label, subtitle, _ in MODES:
            card = ModeCard(key, label, subtitle, self._on_mode_picked)
            cards_row.addWidget(card, 1)
            self._cards[key] = card
        v.addLayout(cards_row, 1)

        nav = QHBoxLayout()
        nav.addStretch(1)
        self.btn_to_config = QPushButton("Next ▶")
        self.btn_to_config.setObjectName("PrimaryAction")
        self.btn_to_config.setEnabled(False)
        self.btn_to_config.clicked.connect(self._goto_config)
        nav.addWidget(self.btn_to_config)
        v.addLayout(nav)
        return page

    def _on_mode_picked(self, key: str):
        self._mode = key
        for k, card in self._cards.items():
            card.set_selected(k == key)
        self.btn_to_config.setEnabled(True)

    # ---------- Page 2: configure ----------

    def _build_config_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        self.cfg_title = QLabel("Configure your station")
        self.cfg_title.setObjectName("StepTitle")
        v.addWidget(self.cfg_title)

        # --- Source group: URL or file list, depending on mode ---
        self.source_box = QGroupBox("1. Source")
        sb = QGridLayout(self.source_box)

        self.url_label = QLabel("URL:")
        self.url_edit = QLineEdit()
        self.url_edit.setPlaceholderText("https://...")
        sb.addWidget(self.url_label, 0, 0)
        sb.addWidget(self.url_edit, 0, 1, 1, 2)

        self.btn_add_files = QPushButton("Add audio files…")
        self.btn_add_files.clicked.connect(self._pick_files)
        self.btn_clear_files = QPushButton("Clear")
        self.btn_clear_files.setObjectName("SmallAction")
        self.btn_clear_files.clicked.connect(self._clear_files)
        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(160)
        sb.addWidget(self.btn_add_files, 1, 0)
        sb.addWidget(self.btn_clear_files, 1, 1)
        sb.addWidget(QLabel(""), 1, 2)
        sb.addWidget(self.file_list, 2, 0, 1, 3)
        v.addWidget(self.source_box)

        # --- Station identity: name + logo, shared by every mode ---
        ident_box = QGroupBox("2. Station name and logo")
        ib = QGridLayout(ident_box)
        ib.addWidget(QLabel("Station name:"), 0, 0)
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. My Drift Mix")
        ib.addWidget(self.name_edit, 0, 1, 1, 2)

        ib.addWidget(QLabel("Logo (PNG/JPG, square works best):"), 1, 0)
        self.logo_path_edit = QLineEdit()
        self.logo_path_edit.setReadOnly(True)
        self.logo_path_edit.setPlaceholderText("Optional — a branded placeholder is generated if empty")
        self.btn_pick_logo = QPushButton("Browse…")
        self.btn_pick_logo.clicked.connect(self._pick_logo)
        ib.addWidget(self.logo_path_edit, 1, 1)
        ib.addWidget(self.btn_pick_logo, 1, 2)

        self.logo_preview = QLabel("no logo")
        self.logo_preview.setObjectName("LogoPreview")
        self.logo_preview.setFixedSize(128, 128)
        ib.addWidget(self.logo_preview, 0, 3, 2, 1)
        v.addWidget(ident_box)

        # --- nav ---
        nav = QHBoxLayout()
        back = QPushButton("◀ Back")
        back.clicked.connect(lambda: self.stack.setCurrentWidget(self.page_mode))
        nav.addWidget(back)
        nav.addStretch(1)
        self.btn_build = QPushButton("Build station ▶")
        self.btn_build.setObjectName("PrimaryAction")
        self.btn_build.clicked.connect(self._start_build)
        nav.addWidget(self.btn_build)
        v.addLayout(nav)
        return page

    def _apply_mode_to_config(self):
        """Show URL row OR file picker row based on the active mode."""
        if self._mode in ("spotify", "youtube"):
            self.url_label.show(); self.url_edit.show()
            self.btn_add_files.hide(); self.btn_clear_files.hide(); self.file_list.hide()
            placeholder = next(p for k, _, _, p in MODES if k == self._mode)
            self.url_edit.setPlaceholderText(placeholder)
            self.source_box.setTitle(f"1. {self._mode.title()} source")
        else:
            self.url_label.hide(); self.url_edit.hide()
            self.btn_add_files.show(); self.btn_clear_files.show(); self.file_list.show()
            self.source_box.setTitle("1. Local audio files")

    def _pick_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Add audio files", "",
            "Audio (*.wav *.mp3 *.m4a *.aac *.flac *.ogg *.opus *.wma);;All files (*.*)",
        )
        for f in files:
            p = Path(f)
            if p not in self._files:
                self._files.append(p)
                self.file_list.addItem(QListWidgetItem(p.name))

    def _clear_files(self):
        self._files.clear()
        self.file_list.clear()

    def _pick_logo(self):
        f, _ = QFileDialog.getOpenFileName(
            self, "Choose station logo", "",
            "Images (*.png *.jpg *.jpeg *.bmp *.webp);;All files (*.*)",
        )
        if not f:
            return
        self._logo_src = Path(f)
        self.logo_path_edit.setText(f)
        pix = QPixmap(f)
        if not pix.isNull():
            self.logo_preview.setPixmap(
                pix.scaled(128, 128, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            )
            self.logo_preview.setText("")

    def _goto_config(self):
        self._apply_mode_to_config()
        self.cfg_title.setText(f"Configure your {self._mode.title()} station")
        self.stack.setCurrentWidget(self.page_config)

    # ---------- Page 3: build progress ----------

    def _build_build_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        t = QLabel("Building your station…")
        t.setObjectName("StepTitle")
        v.addWidget(t)
        self.build_progress = QProgressBar()
        self.build_progress.setRange(0, 100)
        v.addWidget(self.build_progress)
        self.build_log = QPlainTextEdit()
        self.build_log.setReadOnly(True)
        v.addWidget(self.build_log, 1)
        return page

    def _start_build(self):
        if not self._validate():
            return
        slug = safe_slug(self.name_edit.text() or self._mode)
        pdir = make_project_dir(slug)
        music_dir = pdir / "music"

        # Install / generate logo before any long download starts so the user
        # sees their branding committed even if a download later fails.
        if self._logo_src and self._logo_src.exists():
            install_logo(pdir, self._logo_src)
        else:
            make_placeholder_logo(pdir, self.name_edit.text(), self._mode)  # type: ignore[arg-type]

        meta = StationMeta(
            name=self.name_edit.text().strip(),
            source=self._mode,  # type: ignore[arg-type]
            slug=slug,
            logo_path="logo.png",
            source_url=self.url_edit.text().strip() if self._mode != "custom" else "",
        )
        save_meta(pdir, meta)
        self._project_dir = pdir

        self.stack.setCurrentWidget(self.page_build)
        self.build_progress.setValue(0)
        self.build_log.clear()
        self._log(f"Project: {pdir}")
        self._log(f"Mode: {self._mode}")

        url = self.url_edit.text().strip()
        files = list(self._files)
        mode = self._mode

        def build_fn(progress_cb):
            if mode in ("youtube", "spotify"):
                # Pre-flight: make sure yt-dlp.exe is on disk before we start
                # iterating playlist entries, so the download progress isn't
                # interleaved with the one-time install message.
                from ..ytdlp_runtime import ensure_ytdlp
                ensure_ytdlp(progress_cb)

            if mode == "youtube":
                from ..sources import youtube as yt
                entries = yt.fetch_playlist_entries(url, progress=progress_cb)
                progress_cb(0, len(entries), f"Found {len(entries)} entries")
                songs = yt.download_entries(entries, music_dir, progress=progress_cb)
            elif mode == "spotify":
                from ..sources import spotify as sp
                tracks = sp.fetch_playlist_tracks(url)
                progress_cb(0, len(tracks), f"Found {len(tracks)} tracks")
                songs = sp.download_tracks(tracks, music_dir, progress=progress_cb)
            else:
                from ..sources import custom as cu
                songs = cu.import_files(files, music_dir, progress=progress_cb)
            meta.songs = songs
            save_meta(pdir, meta)
            return meta

        worker = BuildWorker(build_fn)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(self._on_progress)
        worker.finished.connect(self._on_build_finished)
        worker.failed.connect(self._on_build_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._task_thread = thread
        self._task_worker = worker
        thread.start()

    def _on_progress(self, done: int, total: int, msg: str):
        if total > 0:
            self.build_progress.setRange(0, total)
            self.build_progress.setValue(done)
        self._log(msg)

    def _on_build_finished(self, meta: StationMeta):
        self._log(f"\n✔ Station ready: {len(meta.songs)} songs.")
        self.done_summary.setText(
            f"Station: {meta.name}\n"
            f"Songs: {len(meta.songs)}\n"
            f"Folder: {self._project_dir}\n\n"
            "Next: open FH6 Radio Tool, set its 'Music folder' to the music/ folder above, "
            "pick a target radio station slot in the game's XML, validate the audio, "
            "then click Generate (or One-Click Replace)."
        )
        pix = QPixmap(str(self._project_dir / "logo.png"))
        if not pix.isNull():
            self.done_logo.setPixmap(pix.scaled(192, 192, Qt.KeepAspectRatio, Qt.SmoothTransformation))
        self.stack.setCurrentWidget(self.page_done)

    def _on_build_failed(self, msg: str):
        self._log(f"\n✖ Build failed:\n{msg}")
        QMessageBox.critical(self, "Build failed", msg.split("\n\n")[0])

    def _log(self, msg: str):
        self.build_log.appendPlainText(msg)

    # ---------- Page 4: done ----------

    def _build_done_page(self) -> QWidget:
        page = QWidget()
        v = QVBoxLayout(page)
        t = QLabel("Station ready")
        t.setObjectName("StepTitle")
        v.addWidget(t)

        row = QHBoxLayout()
        self.done_logo = QLabel()
        self.done_logo.setFixedSize(192, 192)
        self.done_logo.setObjectName("LogoPreview")
        row.addWidget(self.done_logo)
        self.done_summary = QLabel("")
        self.done_summary.setWordWrap(True)
        self.done_summary.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        row.addWidget(self.done_summary, 1)
        v.addLayout(row)

        actions = QHBoxLayout()
        self.btn_open_folder = QPushButton("Open station folder")
        self.btn_open_folder.clicked.connect(self._open_project_folder)
        actions.addWidget(self.btn_open_folder)

        self.btn_open_fh6 = QPushButton("Launch FH6 Radio Tool…")
        self.btn_open_fh6.setObjectName("PrimaryAction")
        self.btn_open_fh6.clicked.connect(self._launch_fh6_tool)
        actions.addWidget(self.btn_open_fh6)

        actions.addStretch(1)
        btn_new = QPushButton("Build another")
        btn_new.clicked.connect(self._reset_to_start)
        actions.addWidget(btn_new)
        v.addLayout(actions)
        v.addStretch(1)
        return page

    def _open_project_folder(self):
        if not getattr(self, "_project_dir", None):
            return
        if sys.platform == "win32":
            os.startfile(self._project_dir)  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["xdg-open", str(self._project_dir)])

    def _launch_fh6_tool(self):
        """Auto-locate and launch the FH6 Radio Tool.

        Order matters: we copy the music-folder path to the clipboard and
        tell the user what to do *before* the FH6 Radio Tool window steals
        focus. We also flip the FH6 tool's UI language to English in its
        SQLite settings so it doesn't start in Chinese, and warn upfront if
        Fmod Bank Tools (a separate external dep the FH6 tool needs to
        actually rebuild banks) isn't configured yet.
        """
        from .. import fh6_tool

        path = fh6_tool.resolve()
        if path is None:
            picked, _ = QFileDialog.getOpenFileName(
                self,
                "Locate FH6 Radio Tool launcher (run_tool.bat or FH6RadioTool.exe)",
                str(Path.home()),
                "FH6 Radio Tool (run_tool.bat FH6RadioTool.exe);;All files (*.*)",
            )
            if not picked:
                return
            path = Path(picked)
            fh6_tool.remember(path)

        # Pre-launch settings written into the FH6 Radio Tool's SQLite so the
        # user does not have to flip these toggles manually:
        #   - ui_language=en so it doesn't start in Chinese.
        #   - fmod_tool=<extracted bundled Fmod_Bank_Tools.exe> so Generate /
        #     One-Click Replace works out of the box.
        try:
            fh6_tool.set_state_setting(path, "ui_language", "en")
        except Exception as exc:
            self._log(f"Could not set FH6 tool language to English: {exc}")

        fmod_exe = None
        try:
            if not fh6_tool.fmod_tool_configured(path):
                fmod_exe = fh6_tool.ensure_fmod_bank_tools()
                if fmod_exe is not None:
                    fh6_tool.set_state_setting(path, "fmod_tool", str(fmod_exe))
                    self._log(f"Configured Fmod Bank Tools: {fmod_exe}")
        except Exception as exc:
            self._log(f"Could not auto-configure Fmod Bank Tools: {exc}")

        music_dir = self._project_dir / "music"
        from PySide6.QtGui import QGuiApplication
        QGuiApplication.clipboard().setText(str(music_dir))

        pre_lines = [
            f"FH6 Radio Tool: {path}",
            "",
            "Your music-folder path is on the clipboard — paste it into the "
            "tool's 'Music folder' field:",
            "",
            str(music_dir),
            "",
        ]
        # If we couldn't supply Fmod Bank Tools (running from a dev checkout
        # with no zip, say), warn so the user isn't surprised by the FH6
        # tool's own error later.
        if not fh6_tool.fmod_tool_configured(path) and fmod_exe is None:
            pre_lines += [
                "⚠ Fmod Bank Tools is not configured in FH6 Radio Tool, and",
                "   no bundled copy was found. You will need to point the",
                "   FH6 Radio Tool at a Fmod_Bank_Tools.exe before Generate",
                "   or One-Click Replace will work.",
                "",
            ]
        pre_lines.append("Click OK to launch the FH6 Radio Tool.")

        QMessageBox.information(
            self, "Launching FH6 Radio Tool",
            "\n".join(pre_lines),
        )

        try:
            fh6_tool.launch(path)
        except Exception as exc:
            QMessageBox.critical(self, "Could not launch", f"{path}\n\n{exc}")
            return

    def _reset_to_start(self):
        self._mode = None
        for c in self._cards.values():
            c.set_selected(False)
        self.btn_to_config.setEnabled(False)
        self.url_edit.clear()
        self.name_edit.clear()
        self.logo_path_edit.clear()
        self.logo_preview.clear(); self.logo_preview.setText("no logo")
        self._logo_src = None
        self._clear_files()
        self.stack.setCurrentWidget(self.page_mode)

    # ---------- validation ----------

    def _validate(self) -> bool:
        if not self.name_edit.text().strip():
            QMessageBox.warning(self, "Missing name", "Please name your station.")
            return False
        if self._mode in ("spotify", "youtube"):
            url = self.url_edit.text().strip()
            if not url.startswith("http"):
                QMessageBox.warning(self, "Missing URL", "Please paste a playlist URL.")
                return False
        else:
            if not self._files:
                QMessageBox.warning(self, "No files", "Please add at least one audio file.")
                return False
        return True
