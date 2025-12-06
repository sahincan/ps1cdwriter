#!/usr/bin/env python3
"""
Simple PS1 CUE burner GUI for Linux using PyQt6 and cdrdao.

Features:
- CD device test using "cdrdao disk-info".
- Optional drive auto-detect using "cdrdao scanbus".
- CUE file selection.
- Burn button that writes with:
    cdrdao write --device <dev> --driver generic-mmc --speed 4 --eject <cue>
- Automatically sets working directory to CUE folder to find .bin files.
- Log area that shows all cdrdao output (stdout + stderr) with timestamps.
- Dark-themed UI for better readability.
"""

import sys
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTextEdit,
    QFileDialog,
    QMessageBox,
)
from PyQt6.QtCore import QDateTime, QProcess


class MainWindow(QMainWindow):
    def __init__(self, parent=None):
        super().__init__(parent)

        self.process = QProcess(self)
        self.drive_ready = False
        self.current_operation = "idle"  # "idle", "test", "burn", "scanbus"

        self.device_edit = None
        self.cue_path_edit = None
        self.test_drive_button = None
        self.auto_detect_button = None
        self.select_cue_button = None
        self.burn_button = None
        self.disc_status_label = None
        self.log_view = None

        self._setup_ui()
        self._setup_process_signals()

    # -------------------------------------------------------
    # UI setup
    # -------------------------------------------------------
    def _setup_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # -------- Drive Section --------
        drive_layout = QHBoxLayout()
        drive_label = QLabel("CD Device:")
        self.device_edit = QLineEdit()
        self.device_edit.setText("/dev/sr0")

        self.test_drive_button = QPushButton("Test Drive")
        self.auto_detect_button = QPushButton("Auto-detect Drive")

        drive_layout.addWidget(drive_label)
        drive_layout.addWidget(self.device_edit)
        drive_layout.addWidget(self.test_drive_button)
        drive_layout.addWidget(self.auto_detect_button)

        # -------- CUE Selection --------
        cue_layout = QHBoxLayout()
        cue_label = QLabel("CUE File:")
        self.cue_path_edit = QLineEdit()
        self.cue_path_edit.setReadOnly(True)

        self.select_cue_button = QPushButton("Select CUE File")

        cue_layout.addWidget(cue_label)
        cue_layout.addWidget(self.cue_path_edit)
        cue_layout.addWidget(self.select_cue_button)

        # -------- Burn Section --------
        status_layout = QHBoxLayout()
        self.disc_status_label = QLabel("Disc status: Unknown")
        self.burn_button = QPushButton("Burn")

        status_layout.addWidget(self.disc_status_label)
        status_layout.addStretch()
        status_layout.addWidget(self.burn_button)

        # -------- Log Output --------
        log_label = QLabel("Log:")
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)

        # Add Layouts
        main_layout.addLayout(drive_layout)
        main_layout.addLayout(cue_layout)
        main_layout.addLayout(status_layout)
        main_layout.addWidget(log_label)
        main_layout.addWidget(self.log_view)

        # Window
        self.setWindowTitle("PS1 CUE Burner")
        self.resize(900, 520)

        # Simple Dark Theme
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2b2b2b;
            }
            QWidget {
                background-color: #2b2b2b;
                color: #f0f0f0;
            }
            QLineEdit, QTextEdit {
                background-color: #3b3b3b;
                color: #f0f0f0;
                border: 1px solid #555;
            }
            QLabel {
                color: #dcdcdc;
            }
            QPushButton {
                background-color: #444;
                color: #f0f0f0;
                border: 1px solid #666;
                padding: 4px;
            }
            QPushButton:hover {
                background-color: #555;
            }
            QPushButton:disabled {
                background-color: #333;
                color: #777;
                border: 1px solid #444;
            }
        """)

        # Connect Signals
        self.test_drive_button.clicked.connect(self.on_test_drive_clicked)
        self.auto_detect_button.clicked.connect(self.on_auto_detect_clicked)
        self.select_cue_button.clicked.connect(self.on_select_cue_clicked)
        self.burn_button.clicked.connect(self.on_burn_clicked)

        self._set_burn_controls_enabled(False)

    # -------------------------------------------------------
    # Process Signals
    # -------------------------------------------------------
    def _setup_process_signals(self):
        self.process.readyReadStandardOutput.connect(self.on_process_stdout)
        self.process.readyReadStandardError.connect(self.on_process_stderr)
        self.process.finished.connect(self.on_process_finished)
        self.process.errorOccurred.connect(self.on_process_error)

    # -------------------------------------------------------
    # Helpers
    # -------------------------------------------------------
    def _append_log(self, text):
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        self.log_view.append(f"[{timestamp}] {text}")

    def _set_burn_controls_enabled(self, enabled):
        if self.burn_button:
            self.burn_button.setEnabled(enabled)

    def _is_cue_file_valid(self):
        path = self.cue_path_edit.text().strip()
        return Path(path).is_file() and path.lower().endswith(".cue")

    def _process_is_running(self):
        return self.process.state() != QProcess.ProcessState.NotRunning

    # -------------------------------------------------------
    # UI Slots
    # -------------------------------------------------------
    def on_test_drive_clicked(self):
        if self._process_is_running():
            return

        device = self.device_edit.text().strip()
        if not device:
            QMessageBox.warning(self, "Invalid Device", "Enter a valid device path.")
            return

        self._append_log(f"Testing drive: {device}")
        self.current_operation = "test"
        self.process.setProgram("cdrdao")
        self.process.setArguments(["disk-info", "--device", device])
        self.process.start()

        self.drive_ready = False
        self.disc_status_label.setText("Disc status: Testing...")
        self._set_burn_controls_enabled(False)

    def on_auto_detect_clicked(self):
        if self._process_is_running():
            return

        self._append_log("Running auto-detect (cdrdao scanbus)...")
        self.current_operation = "scanbus"
        self.process.setProgram("cdrdao")
        self.process.setArguments(["scanbus"])
        self.process.start()

    def on_select_cue_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select PS1 CUE File",
            "",
            "CUE Files (*.cue);;All Files (*)",
        )
        if file_path:
            self.cue_path_edit.setText(file_path)
            self._append_log(f"Selected CUE: {file_path}")
            self._set_burn_controls_enabled(self.drive_ready and self._is_cue_file_valid())

    def on_burn_clicked(self):
        if self._process_is_running():
            return

        if not self.drive_ready:
            QMessageBox.warning(self, "Drive Not Ready", "Run Test Drive first.")
            return

        if not self._is_cue_file_valid():
            QMessageBox.warning(self, "Invalid CUE", "Select a valid .cue file.")
            return

        device = self.device_edit.text().strip()
        cue_path = self.cue_path_edit.text().strip()

        # Set working directory so CUE finds .bin file
        cue_dir = str(Path(cue_path).parent)
        self.process.setWorkingDirectory(cue_dir)

        self._append_log("Starting burn process...")
        self._append_log(f"Device={device}, Driver=generic-mmc, Speed=4")

        self.current_operation = "burn"
        self.process.setProgram("cdrdao")
        self.process.setArguments([
            "write", "--device", device, "--driver", "generic-mmc",
            "--speed", "4", "--eject", cue_path
        ])
        self.process.start()

        self.disc_status_label.setText("Disc status: Burning...")
        self._set_burn_controls_enabled(False)

    # -------------------------------------------------------
    # Process Output
    # -------------------------------------------------------
    def on_process_stdout(self):
        text = bytes(self.process.readAllStandardOutput()).decode().strip()
        if text:
            for line in text.splitlines():
                self._append_log(line)

    def on_process_stderr(self):
        text = bytes(self.process.readAllStandardError()).decode().strip()
        if text:
            for line in text.splitlines():
                self._append_log(line)

    def on_process_finished(self, exit_code, _):
        op = self.current_operation
        self._append_log(f"Process finished (op={op}, code={exit_code})")

        if op == "test":
            if exit_code == 0:
                self.drive_ready = True
                self.disc_status_label.setText("Disc status: Ready")
            else:
                self.disc_status_label.setText("Disc status: Drive test failed")

        elif op == "burn":
            if exit_code == 0:
                self.disc_status_label.setText("Disc status: Burn completed")
            else:
                self.disc_status_label.setText("Disc status: Burn failed")

        elif op == "scanbus":
            for candidate in ("/dev/sr0", "/dev/cdrom", "/dev/dvd"):
                if Path(candidate).exists():
                    self.device_edit.setText(candidate)
                    self._append_log(f"Auto-selected drive: {candidate}")
                    break

        self._set_burn_controls_enabled(self.drive_ready and self._is_cue_file_valid())
        self.current_operation = "idle"

    def on_process_error(self, error):
        self._append_log("Process error occurred.")
        self.disc_status_label.setText("Disc status: Error")
        self.drive_ready = False
        self._set_burn_controls_enabled(False)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

