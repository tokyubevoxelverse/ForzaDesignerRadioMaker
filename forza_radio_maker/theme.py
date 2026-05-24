"""Visual theme reused from FH6 Radio Tool v3.x.

Keeps the look-and-feel consistent so users moving between the two tools
get the same fonts, spacing, and button sizing. Adds a light extension of
mode-card and accent-button styles that are specific to this app.
"""
from __future__ import annotations

# Base QSS lifted from fh6_radio_tool/v2_ui.py so the two tools render
# QGroupBox / QPushButton / table headers identically.
BASE_QSS = """
QGroupBox { margin-top: 6px; padding-top: 8px; }
QLabel#SectionTitle { padding: 0px 0px 2px 0px; font-weight: 500; }
QLabel#StepTitle { font-size: 15px; font-weight: 600; padding: 4px 0px; }
QLabel#CompactHint { color: #555; padding-top: 2px; }
QPushButton { padding: 4px 10px; min-height: 26px; }
QPushButton#PrimaryAction { padding: 6px 14px; min-height: 32px; font-weight: 500; }
QPushButton#DangerAction { padding: 6px 14px; min-height: 32px; font-weight: 500; }
QPushButton#BackupAction { padding: 4px 10px; min-height: 26px; }
QPushButton#SmallAction { padding: 3px 8px; min-height: 24px; }
QPushButton#SideTab { padding: 5px 12px; min-height: 30px; font-weight: 500; text-align: left; }
QLineEdit, QComboBox { min-height: 25px; }
QTableWidget { gridline-color: #dddddd; }
QHeaderView::section { padding: 4px 6px; }
"""

# Additions for the wizard / mode-card layout used by this app.
EXTRA_QSS = """
QFrame#ModeCard {
    background-color: #fafafa;
    border: 1px solid #d0d0d0;
    border-radius: 8px;
    padding: 12px;
}
QFrame#ModeCard[selected="true"] {
    border: 2px solid #1d72b8;
    background-color: #eef6fc;
}
QLabel#ModeTitle { font-size: 16px; font-weight: 600; }
QLabel#ModeSubtitle { color: #555; }
QLabel#LogoPreview {
    border: 1px dashed #bbb;
    background-color: #fff;
    qproperty-alignment: AlignCenter;
}
QPushButton#PrimaryAction {
    background-color: #1d72b8;
    color: white;
    border: 1px solid #155a93;
    border-radius: 4px;
}
QPushButton#PrimaryAction:hover { background-color: #2585cf; }
QPushButton#PrimaryAction:disabled { background-color: #b0bec5; color: #eceff1; border-color: #90a4ae; }
"""

FULL_QSS = BASE_QSS + EXTRA_QSS
