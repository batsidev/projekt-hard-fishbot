"""Desktop launcher for running fisher.py with a small PySide6 GUI.

The launcher starts the main script as an unbuffered subprocess, streams its
combined stdout/stderr output into the window, and emits a Windows notification
sound when the script reports a new message.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

PROJECT_ROOT = Path(__file__).resolve().parent
FISHER_SCRIPT = PROJECT_ROOT / "fisher.py"
NOTIFICATION_TEXT = "New message detected"
FISHER_CHILD_ARG = "--run-fisher-child"


def is_frozen_app() -> bool:
    """Return True when running from a PyInstaller executable."""
    return bool(getattr(sys, "frozen", False))


def executable_dir() -> Path:
    """Return the directory containing the executable or source script."""
    if is_frozen_app():
        return Path(sys.executable).resolve().parent
    return PROJECT_ROOT


class FisherWorker(QThread):
    """Runs fisher.py in a subprocess and streams output without blocking Qt."""

    output_received = Signal(str)
    process_started = Signal()
    process_finished = Signal(int, str)
    process_error = Signal(str)

    def __init__(self, project_root: Path, script_path: Path) -> None:
        super().__init__()
        self.project_root = project_root
        self.script_path = script_path
        self._process: Optional[subprocess.Popen[str]] = None
        self._lock = threading.Lock()
        self._stop_requested = threading.Event()
        self._terminator: Optional[threading.Thread] = None

    def run(self) -> None:
        if is_frozen_app():
            command = [sys.executable, FISHER_CHILD_ARG]
            working_directory = executable_dir()
            startup_description = f"{Path(sys.executable).name} {FISHER_CHILD_ARG}"
        else:
            if not self.script_path.exists():
                self.process_error.emit(f"[GUI] Errore: file non trovato: {self.script_path}\n")
                self.process_finished.emit(-1, "fisher.py non trovato")
                return

            command = [sys.executable, "-u", str(self.script_path.name)]
            working_directory = self.project_root
            startup_description = "python -u fisher.py"

        self.output_received.emit(f"[GUI] Avvio: {startup_description}\n")
        creation_flags = 0
        if os.name == "nt":
            creation_flags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

        try:
            process = subprocess.Popen(
                command,
                cwd=str(working_directory),
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                creationflags=creation_flags,
            )
        except Exception as exc:  # Show startup failures in the GUI console.
            self.process_error.emit(f"[GUI] Errore durante l'avvio di fisher.py: {exc}\n")
            self.process_finished.emit(-1, "errore di avvio")
            return

        with self._lock:
            self._process = process
        self.process_started.emit()

        try:
            assert process.stdout is not None
            for line in process.stdout:
                self.output_received.emit(line)
        except Exception as exc:
            self.process_error.emit(f"[GUI] Errore durante la lettura dei log: {exc}\n")
        finally:
            return_code = process.wait()
            with self._lock:
                self._process = None
            reason = "arrestato" if self._stop_requested.is_set() else "terminato"
            self.process_finished.emit(return_code, reason)

    def request_stop(self) -> None:
        """Stop the child process asynchronously so the GUI remains responsive."""
        self._stop_requested.set()
        with self._lock:
            process = self._process

        if process is None or process.poll() is not None:
            return

        if self._terminator and self._terminator.is_alive():
            return

        self._terminator = threading.Thread(
            target=self._stop_process,
            args=(process,),
            name="fisher-process-terminator",
            daemon=True,
        )
        self._terminator.start()

    def _stop_process(self, process: subprocess.Popen[str]) -> None:
        try:
            if os.name == "nt":
                try:
                    self.output_received.emit("[GUI] Invio CTRL_BREAK_EVENT a fisher.py...\n")
                    process.send_signal(signal.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
                    process.wait(timeout=5)
                    return
                except Exception as exc:
                    self.output_received.emit(
                        f"[GUI] Warning: CTRL_BREAK_EVENT non riuscito: {exc}. "
                        "Procedo con terminate().\n"
                    )
            else:
                try:
                    self.output_received.emit("[GUI] Invio SIGTERM a fisher.py...\n")
                    process.terminate()
                    process.wait(timeout=5)
                    return
                except subprocess.TimeoutExpired:
                    pass

            if process.poll() is None:
                self.output_received.emit("[GUI] Arresto con terminate()...\n")
                process.terminate()
                try:
                    process.wait(timeout=3)
                    return
                except subprocess.TimeoutExpired:
                    pass

            if process.poll() is None:
                self.output_received.emit("[GUI] Arresto forzato con kill()...\n")
                process.kill()
                process.wait(timeout=3)
        except Exception as exc:
            self.process_error.emit(f"[GUI] Errore durante l'arresto di fisher.py: {exc}\n")


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Fisher Desktop Launcher")
        self.resize(900, 600)

        self.worker: Optional[FisherWorker] = None
        self._running = False
        self._stop_in_progress = False
        self._close_after_stop = False

        self.status_label = QLabel("Stato: fermo")
        self.toggle_button = QPushButton("Start")
        self.console = QTextEdit()
        self.console.setReadOnly(True)
        self.console.setLineWrapMode(QTextEdit.NoWrap)

        layout = QVBoxLayout()
        layout.addWidget(self.status_label)
        layout.addWidget(self.toggle_button)
        layout.addWidget(self.console)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        self.toggle_button.clicked.connect(self.toggle_process)

    def toggle_process(self) -> None:
        if self._running:
            self.stop_process()
        else:
            self.start_process()

    def start_process(self) -> None:
        if self.worker is not None or self._running:
            return

        self.toggle_button.setEnabled(False)

        self.worker = FisherWorker(PROJECT_ROOT, FISHER_SCRIPT)
        self.worker.output_received.connect(self.handle_output)
        self.worker.process_error.connect(self._append_console)
        self.worker.process_started.connect(self.handle_started)
        self.worker.process_finished.connect(self.handle_finished)
        self.worker.start()

    def stop_process(self) -> None:
        if not self.worker or self._stop_in_progress:
            return

        self._stop_in_progress = True
        self.status_label.setText("Stato: arresto in corso")
        self.toggle_button.setEnabled(False)
        self.worker.request_stop()

    def handle_started(self) -> None:
        self._running = True
        self._stop_in_progress = False
        self.status_label.setText("Stato: in esecuzione")
        self.toggle_button.setText("Stop")
        self.toggle_button.setEnabled(True)

    def handle_finished(self, return_code: int, reason: str) -> None:
        self._append_console(f"[GUI] Processo {reason} con codice di uscita {return_code}.\n")
        if self.worker is not None:
            self.worker.deleteLater()
            self.worker = None

        self._running = False
        self._stop_in_progress = False
        self.status_label.setText("Stato: fermo")
        self.toggle_button.setText("Start")
        self.toggle_button.setEnabled(True)

        if self._close_after_stop:
            self._close_after_stop = False
            self.close()

    def handle_output(self, text: str) -> None:
        self._append_console(text)
        if NOTIFICATION_TEXT in text:
            self._append_console(f"[GUI] Notifica rilevata: {NOTIFICATION_TEXT}\n")
            self._beep()

    def _append_console(self, text: str) -> None:
        self.console.moveCursor(QTextCursor.End)
        self.console.insertPlainText(text)
        self.console.moveCursor(QTextCursor.End)

    def _beep(self) -> None:
        if os.name == "nt":
            try:
                import winsound

                winsound.MessageBeep(winsound.MB_ICONEXCLAMATION)
                return
            except Exception as exc:
                self._append_console(f"[GUI] winsound non disponibile: {exc}\n")
        QApplication.beep()

    def closeEvent(self, event) -> None:  # type: ignore[override]
        if not self._running:
            event.accept()
            return

        reply = QMessageBox.question(
            self,
            "Fisher in esecuzione",
            "fisher.py è ancora in esecuzione. Vuoi fermarlo prima di chiudere?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            event.ignore()
            self._close_after_stop = True
            self.stop_process()
        else:
            event.ignore()


def run_fisher_child() -> int:
    """Run the bundled fisher module in a subprocess of the frozen executable."""
    try:
        sys.stdout.reconfigure(line_buffering=True, write_through=True)
        sys.stderr.reconfigure(line_buffering=True, write_through=True)
    except Exception:
        pass

    os.environ["PYTHONUNBUFFERED"] = "1"

    print("[GUI/FISHER] Child process started.", flush=True)
    print(f"[GUI/FISHER] Current working directory: {Path.cwd()}", flush=True)
    print(f"[GUI/FISHER] Executable: {sys.executable}", flush=True)

    if FISHER_CHILD_ARG in sys.argv:
        sys.argv.remove(FISHER_CHILD_ARG)

    import fisher  # noqa: F401 - importing starts the existing fisher script.

    return 0


def main() -> int:
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    if FISHER_CHILD_ARG in sys.argv:
        raise SystemExit(run_fisher_child())
    raise SystemExit(main())
