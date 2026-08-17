"""M1 stub — unblocks the backend while the real model trains.

TEMPORARY. Overwritten in Step 5 with the trained-model implementation.
The signatures here are the frozen contract and will not change.
"""

from pathlib import Path

_DIR = Path(__file__).resolve().parent


def load_model(path=None):
    """No-op stub. Real implementation lands in Step 5."""
    return None


def predict_rul(window):
    c = window[-1]["cycle"]
    rul = max(0.0, 125.0 - c * 0.55)
    return (rul, rul * 0.75, rul * 1.25)
