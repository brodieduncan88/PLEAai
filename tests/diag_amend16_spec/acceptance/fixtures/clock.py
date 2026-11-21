"""An injectable clock for one party (testability requirement TR-CLOCK: the mailbox and the courier take ALL time from
an object of this shape, so a test can suspend, reboot and set the wall clock).

    boottime_ns()   stands for time.clock_gettime_ns(time.CLOCK_BOOTTIME)   (M-T-1) - counts suspension
    monotonic_ns()  stands for CLOCK_MONOTONIC / time.monotonic_ns()       - does NOT count suspension
    wall()          stands for time.time()                                  (M-T-4, M-T-5)
    boot_id()       stands for /proc/sys/kernel/random/boot_id              (M-T-2)

Operations a test performs:
    advance(s)      s seconds pass while running: every clock moves by s
    suspend(s)      the machine is suspended for s seconds: BOOTTIME and the wall clock move, MONOTONIC does not
    set_wall(d)     the wall clock is set by d seconds (negative: backwards); nothing else moves
    reboot(down=s)  the machine restarts after s seconds down: BOOTTIME and MONOTONIC start again near zero, a new
                    boot identifier, the wall clock moves by s
An implementation that reads the real clocks directly, or reads monotonic_ns() for an age, fails the M-T-1, M-T-3 and
M-T-5 tests by construction.
"""
import threading
import uuid


class TestClock:
    __test__ = False

    def __init__(self, wall_start=1_800_000_000.0, boot_start_s=1000.0):
        self._lock = threading.Lock()
        self._boot = int(boot_start_s * 1e9)
        self._mono = int(boot_start_s * 1e9)
        self._wall = float(wall_start)
        self._boot_id = str(uuid.uuid4())
        self.reboots = 0

    def boottime_ns(self) -> int:
        with self._lock:
            return self._boot

    def monotonic_ns(self) -> int:
        with self._lock:
            return self._mono

    def wall(self) -> float:
        with self._lock:
            return self._wall

    def boot_id(self) -> str:
        with self._lock:
            return self._boot_id

    def advance(self, s: float):
        with self._lock:
            self._boot += int(s * 1e9); self._mono += int(s * 1e9); self._wall += s

    def suspend(self, s: float):
        with self._lock:
            self._boot += int(s * 1e9); self._wall += s

    def set_wall(self, d: float):
        with self._lock:
            self._wall += d

    def reboot(self, down: float = 5.0):
        with self._lock:
            self._boot = int(0.5e9); self._mono = int(0.5e9); self._wall += down
            self._boot_id = str(uuid.uuid4()); self.reboots += 1
