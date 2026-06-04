import time

LOG_FILENAME = "debug.log"
MAX_LOG_BYTES = 65536  # 64 KB — rotate before filling flash


def _rotate():
    """Keep the log from growing unbounded by trimming the oldest half."""
    try:
        with open(LOG_FILENAME, "r") as f:
            data = f.read()
        with open(LOG_FILENAME, "w") as f:
            f.write(data[len(data) // 2 :])
    except Exception:
        # If rotation fails just wipe it and start fresh
        try:
            with open(LOG_FILENAME, "w") as f:
                f.write("")
        except Exception:
            pass


def _size():
    try:
        import os

        return os.stat(LOG_FILENAME)[6]
    except Exception:
        return 0


def log(msg, rtc=None):
    """Write a timestamped line to debug.log and also print it."""
    if rtc is not None:
        t = rtc.datetime()
        prefix = "{:04d}-{:02d}-{:02d}T{:02d}:{:02d}:{:02d}".format(
            t[0], t[1], t[2], t[4], t[5], t[6]
        )
    else:
        prefix = str(time.ticks_ms())

    line = f"[{prefix}] {msg}\n"
    print(line, end="")

    if _size() >= MAX_LOG_BYTES:
        _rotate()

    try:
        with open(LOG_FILENAME, "a") as f:
            f.write(line)
    except Exception as e:
        print(f"[log] Failed to write: {e}")
