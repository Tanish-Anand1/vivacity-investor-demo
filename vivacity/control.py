"""Cooperative worker pause. This never rewinds, replays, or replaces simulator state."""
import threading
import time


class PauseControl:
    def __init__(self):
        self.condition = threading.Condition()
        self.requested = False
        self.acknowledged = False
        self.since = None
        self.total = 0.

    def pause(self):
        with self.condition:
            self.requested = True

    def resume(self):
        with self.condition:
            if self.since is not None:
                self.total += time.perf_counter()-self.since
            self.since = None
            self.requested = self.acknowledged = False
            self.condition.notify_all()

    def checkpoint(self, cancel, keep_alive=None):
        with self.condition:
            while self.requested and not cancel.is_set():
                if keep_alive is not None and not keep_alive():
                    cancel.set()
                    break
                if not self.acknowledged:
                    self.acknowledged = True
                    self.since = time.perf_counter()
                self.condition.wait(.05)
            return not cancel.is_set()

    def elapsed(self):
        with self.condition:
            return self.total + (time.perf_counter()-self.since if self.since is not None else 0.)

    def state(self):
        with self.condition:
            return {'pause_requested':self.requested,'paused':self.acknowledged,'paused_seconds':self.elapsed()}
