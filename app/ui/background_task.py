from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot


class BackgroundWorker(QObject):
    """Qt arka plan iş parçacığında tek bir ağ/IO işini çalıştırır."""

    finished = Signal(object)
    failed = Signal(object)

    def __init__(self, operation):
        super().__init__()
        self._operation = operation

    @Slot()
    def run(self) -> None:
        try:
            self.finished.emit(self._operation())
        except Exception as error:  # UI thread must receive the failure safely.
            self.failed.emit(error)
