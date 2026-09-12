"""One local IO task; results and cleanup are delivered on the GUI thread."""
from PySide6.QtCore import QObject, QThread, Signal, Slot
from app.ui.background_task import BackgroundWorker


class LocalTask(QObject):
    succeeded = Signal(object)
    failed = Signal(object)
    settled = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._thread = None
        self._worker = None
        self._result = None
        self._error = None
        self._finishing = False

    @property
    def busy(self):
        return self._thread is not None or self._finishing

    def start(self, operation):
        if self.busy:
            return False
        self._result = self._error = None
        thread = QThread(self)
        worker = BackgroundWorker(operation)
        worker.moveToThread(thread)
        self._thread, self._worker = thread, worker
        thread.started.connect(worker.run)
        worker.finished.connect(self._success)
        worker.failed.connect(self._failure)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._finish)
        thread.start()
        return True

    @Slot(object)
    def _success(self, result):
        self._result = result
        self._thread.quit()

    @Slot(object)
    def _failure(self, error):
        self._error = error
        self._thread.quit()

    @Slot()
    def _finish(self):
        self._finishing = True
        self._thread.deleteLater()
        self._thread = self._worker = None
        result, error = self._result, self._error
        self._result = self._error = None
        try:
            if error is not None:
                self.failed.emit(error)
            else:
                self.succeeded.emit(result)
        finally:
            self._finishing = False
            self.settled.emit()
