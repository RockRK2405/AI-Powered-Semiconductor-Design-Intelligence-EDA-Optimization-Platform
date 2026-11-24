"""Test-session settings."""

import os

# Keep numeric libraries single-threaded in tests, so a test run never competes for CPU with a
# concurrent EDA sweep (runtime labels are sensitive to contention).
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
