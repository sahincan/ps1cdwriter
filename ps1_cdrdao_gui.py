#!/usr/bin/env python3
"""
Simple PS1 CUE burner GUI for Linux using PyQt6 and cdrdao.

Features:
- CD device test using "cdrdao disk-info".
- Optional drive auto-detect using "cdrdao scanbus".
- CUE file selection.
- Burn button that writes with:
    cdrdao write --device <dev> --driver generic-mmc --speed 4 --eject <cue>
- Log area that shows all cdrdao output (stdout + stderr) with timestamps.
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

        # Tracks what the current cdrdao operation is
        # Possible values: "idle", "test", "burn", "scanbus"
        self.current_operation = "idle"

        self.device_edit: QLineEdit | None = None
        self.cue_path_edit: QLineEdit | None = None
        self.test_drive_button: QPushButton | None = None
        self.auto_detect_button: QPushButton | None = None
        self.select_cue_button: QPushButton | None = None
        self.burn_button: QPushButton | None = None
        self.disc_status_label: QLabel | None = None
        self.log_view: QTextEdit | None = None

        self._setup_ui()
        self._setup_process_signals()

    # -------------------------------------------------------
    # UI setup
    # -------------------------------------------------------
    def _setup_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        main_layout = QVBoxLayout(central)

        # --- Drive section ---
        drive_layout = QHBoxLayout()
        drive_label = QLabel("CD Device:", self)
        self.device_edit = QLineEdit(self)
        self.device_edit.setText("/dev/sr0")  # Common default CD/DVD device on Linux

        self.test_drive_button = QPushButton("Test Drive", self)
        self.auto_detect_button = QPushButton("Auto-detect Drive", self)

        drive_layout.addWidget(drive_label)
        drive_layout.addWidget(self.device_edit)
        drive_layout.addWidget(self.test_drive_button)
        drive_layout.addWidget(self.auto_detect_button)

        # --- CUE selection section ---
        cue_layout = QHBoxLayout()
        cue_label = QLabel("CUE File:", self)
        self.cue_path_edit = QLineEdit(self)
        self.cue_path_edit.setReadOnly(True)

        self.select_cue_button = QPushButton("Select CUE File", self)

        cue_layout.addWidget(cue_label)
        cue_layout.addWidget(self.cue_path_edit)
        cue_layout.addWidget(self.select_cue_button)

        # --- Disc status + burn button ---
        status_layout = QHBoxLayout()
        self.disc_status_label = QLabel("Disc status: Unknown", self)
        self.burn_button = QPushButton("Burn", self)

        status_layout.addWidget(self.disc_status_label)
        status_layout.addStretch(1)
        status_layout.addWidget(self.burn_button)

        # --- Log view ---
        log_label = QLabel("Log:", self)
        self.log_view = QTextEdit(self)
        self.log_view.setReadOnly(True)

        # Put everything in main layout
        main_layout.addLayout(drive_layout)
        main_layout.addLayout(cue_layout)
        main_layout.addLayout(status_layout)
        main_layout.addWidget(log_label)
        main_layout.addWidget(self.log_view)

        # Window settings
        self.setWindowTitle("PS1 CUE Burner (cdrdao Frontend)")
        self.resize(900, 520)

        # Connect UI signals
        self.test_drive_button.clicked.connect(self.on_test_drive_clicked)
        self.auto_detect_button.clicked.connect(self.on_auto_detect_clicked)
        self.select_cue_button.clicked.connect(self.on_select_cue_clicked)
        self.burn_button.clicked.connect(self.on_burn_clicked)

        # Disable burn at startup until drive + cue file are ready
        self._set_burn_controls_enabled(False)

    def _setup_process_signals(self) -> None:
        self.process.readyReadStandardOutput.connect(self.on_process_stdout)
        self.process.readyReadStandardError.connect(self.on_process_stderr)
        self.process.finished.connect(self.on_process_finished)
        self.process.errorOccurred.connect(self.on_process_error)

    # -------------------------------------------------------
    # Helper methods
    # -------------------------------------------------------
    def _append_log(self, text: str) -> None:
        """Append a timestamped line to the log view."""
        if not self.log_view:
            return
        timestamp = QDateTime.currentDateTime().toString("yyyy-MM-dd hh:mm:ss")
        self.log_view.append(f"[{timestamp}] {text}")

    def _set_burn_controls_enabled(self, enabled: bool) -> None:
        if self.burn_button:
            self.burn_button.setEnabled(enabled)

    def _is_cue_file_valid(self) -> bool:
        """Check that a .cue file exists and has the correct extension."""
        if not self.cue_path_edit:
            return False

        path_str = self.cue_path_edit.text().strip()
        if not path_str:
            return False

        path = Path(path_str)
        return path.is_file() and path.suffix.lower() == ".cue"

    def _process_is_running(self) -> bool:
        return self.process.state() != QProcess.ProcessState.NotRunning

    # -------------------------------------------------------
    # UI slots
    # -------------------------------------------------------
    def on_test_drive_clicked(self) -> None:
        if self._process_is_running():
            QMessageBox.warning(
                self,
                "Process Running",
                "Another operation is currently running. Please wait.",
            )
            return

        if not self.device_edit:
            return

        device = self.device_edit.text().strip()
        if not device:
            QMessageBox.warning(
                self,
                "Invalid Device",
                "Please enter a valid CD device path, e.g. /dev/sr0.",
            )
            return

        self._append_log(f"Testing drive using device: {device}")

        # cdrdao disk-info --device <device>
        program = "cdrdao"
        args = ["disk-info", "--device", device]

        self.current_operation = "test"
        self.process.setProgram(program)
        self.process.setArguments(args)
        self.process.start()

        if not self.process.waitForStarted(1000):
            self._append_log("Failed to start cdrdao. Is it installed?")
            QMessageBox.critical(
                self,
                "Error",
                "Failed to start cdrdao. Make sure it is installed and you have permissions.",
            )
            self.current_operation = "idle"
            return

        self.drive_ready = False
        if self.disc_status_label:
            self.disc_status_label.setText("Disc status: Testing...")
        self._set_burn_controls_enabled(False)

    def on_auto_detect_clicked(self) -> None:
        """Run 'cdrdao scanbus' and try to auto-detect a CD device."""
        if self._process_is_running():
            QMessageBox.warning(
                self,
                "Process Running",
                "Another operation is currently running. Please wait.",
            )
            return

        self._append_log("Running 'cdrdao scanbus' for drive detection...")

        program = "cdrdao"
        args = ["scanbus"]

        self.current_operation = "scanbus"
        self.process.setProgram(program)
        self.process.setArguments(args)
        self.process.start()

        if not self.process.waitForStarted(1000):
            self._append_log("Failed to start 'cdrdao scanbus'.")
            QMessageBox.critical(
                self,
                "Error",
                "Failed to start 'cdrdao scanbus'. Check installation and permissions.",
            )
            self.current_operation = "idle"
            return

    def on_select_cue_clicked(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select PS1 CUE File",
            "",
            "CUE Files (*.cue);;All Files (*)",
        )

        if file_path and self.cue_path_edit:
            self.cue_path_edit.setText(file_path)
            self._append_log(f"Selected CUE file: {file_path}")

            # Enable burn if drive is ready and CUE file is valid
            self._set_burn_controls_enabled(self.drive_ready and self._is_cue_file_valid())
        else:
            # User cancelled or no file selected
            self._set_burn_controls_enabled(False)

    def on_burn_clicked(self) -> None:
        if self._process_is_running():
            QMessageBox.warning(
                self,
                "Process Running",
                "Another operation is currently running. Please wait.",
            )
            return

        if not self.drive_ready:
            QMessageBox.warning(
                self,
                "Drive Not Ready",
                "Please test the drive first.",
            )
            return

        if not self._is_cue_file_valid():
            QMessageBox.warning(
                self,
                "Invalid CUE",
                "Please select a valid .cue file.",
            )
            return

        if not (self.device_edit and self.cue_path_edit):
            return

        device = self.device_edit.text().strip()
        cue_path = self.cue_path_edit.text().strip()

        self._append_log(
            f"Starting burn process with settings:"
            f" device={device}, driver=generic-mmc, speed=4, eject=yes"
        )

        # This matches your successful terminal command:
        #   cdrdao write --device /dev/sr0 --driver generic-mmc --speed 4 <CUE>
        program = "cdrdao"
        args = [
            "write",
            "--device",
            device,
            "--driver",
            "generic-mmc",
            "--speed",
            "4",
            "--eject",
            cue_path,
        ]

        self.current_operation = "burn"
        self.process.setProgram(program)
        self.process.setArguments(args)
        self.process.start()

        if not self.process.waitForStarted(1000):
            self._append_log("Failed to start burn process.")
            QMessageBox.critical(
                self,
                "Error",
                "Failed to start cdrdao. Check installation and permissions.",
            )
            self.current_operation = "idle"
            return

        if self.disc_status_label:
            self.disc_status_label.setText("Disc status: Burning...")
        self._set_burn_controls_enabled(False)

    # -------------------------------------------------------
    # QProcess handlers
    # -------------------------------------------------------
    def on_process_stdout(self) -> None:
        data = self.process.readAllStandardOutput()
        text = bytes(data).decode(errors="ignore").strip()
        if text:
            for line in text.splitlines():
                self._append_log(line)

    def on_process_stderr(self) -> None:
        data = self.process.readAllStandardError()
        text = bytes(data).decode(errors="ignore").strip()
        if text:
            for line in text.splitlines():
                self._append_log(line)

    def on_process_finished(self, exit_code: int, exit_status: QProcess.ExitStatus) -> None:
        self._append_log(
            f"Process finished (operation={self.current_operation}) "
            f"with exit code {exit_code}"
        )

        op = self.current_operation

        if op == "test":
            if exit_code == 0:
                self.drive_ready = True
                if self.disc_status_label:
                    self.disc_status_label.setText("Disc status: Ready")
                self._append_log("Drive test successful. Disc appears to be readable.")
            else:
                self.drive_ready = False
                if self.disc_status_label:
                    self.disc_status_label.setText("Disc status: Drive test failed")
                self._append_log("Drive test failed. Check disc and device path.")

        elif op == "burn":
            if exit_code == 0:
                if self.disc_status_label:
                    self.disc_status_label.setText("Disc status: Burn completed")
                self._append_log("Burn completed successfully.")
            else:
                if self.disc_status_label:
                    self.disc_status_label.setText("Disc status: Burn failed")
                self._append_log("Burn failed. Please check the log output above.")

        elif op == "scanbus":
            if exit_code == 0:
                self._append_log("'cdrdao scanbus' completed successfully.")
                # Try simple auto-select of common device paths
                for candidate in ("/dev/sr0", "/dev/cdrom", "/dev/dvd"):
                    if Path(candidate).exists():
                        if self.device_edit:
                            self.device_edit.setText(candidate)
                        self._append_log(f"Auto-selected device: {candidate}")
                        break
                else:
                    self._append_log(
                        "No common device path (/dev/sr0, /dev/cdrom, /dev/dvd) found. "
                        "Please set the CD device manually."
                    )
            else:
                self._append_log("'cdrdao scanbus' failed. Check the log output.")

        # After any operation, update burn button state
        self._set_burn_controls_enabled(self.drive_ready and self._is_cue_file_valid())

        # Back to idle
        self.current_operation = "idle"

    def on_process_error(self, error: QProcess.ProcessError) -> None:
        if error == QProcess.ProcessError.FailedToStart:
            msg = "Process error: Failed to start. Is cdrdao installed and in PATH?"
        elif error == QProcess.ProcessError.Crashed:
            msg = "Process error: cdrdao crashed."
        elif error == QProcess.ProcessError.Timedout:
            msg = "Process error: Timed out."
        elif error == QProcess.ProcessError.WriteError:
            msg = "Process error: Write error."
        elif error == QProcess.ProcessError.ReadError:
            msg = "Process error: Read error."
        else:
            msg = "Process error: Unknown error."

        self._append_log(msg)
        QMessageBox.critical(self, "Process Error", msg)

        # After an error, we disable burning until drive is tested again
        self.drive_ready = False
        if self.disc_status_label:
            self.disc_status_label.setText("Disc status: Error")
        self._set_burn_controls_enabled(False)
        self.current_operation = "idle"


def main() -> None:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()

