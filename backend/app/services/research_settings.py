"""
Research V2 limits.

These bound the cost and duration of one research run.
Every value can be overridden with an environment variable
of the same name, e.g. ORION_MAX_TOTAL_PAPERS=60.
"""

import os


def _int_setting(name, default):
    value = os.getenv(name)

    if value is None or not value.strip():
        return default

    try:
        return max(0, int(value))
    except ValueError:
        print(f"[SETTINGS] Ignoring invalid {name}={value!r}")
        return default


# Longest research question accepted, in characters.
MAX_QUESTION_CHARS = _int_setting("ORION_MAX_QUESTION_CHARS", 500)

# Sub-questions the planner may create.
MAX_SUB_QUESTIONS = _int_setting("ORION_MAX_SUB_QUESTIONS", 8)

# Papers requested from OpenAlex per sub-question.
PAPERS_PER_QUERY = _int_setting("ORION_PAPERS_PER_QUERY", 10)

# Unique papers kept per research run (all sub-questions).
MAX_TOTAL_PAPERS = _int_setting("ORION_MAX_TOTAL_PAPERS", 40)

# Papers without full text whose abstracts are read.
MAX_ABSTRACT_PAPERS = _int_setting("ORION_MAX_ABSTRACT_PAPERS", 20)

# Abstracts sent to the model in one extraction call.
ABSTRACTS_PER_CALL = max(1, _int_setting("ORION_ABSTRACTS_PER_CALL", 8))

# Largest PDF downloaded, in megabytes.
MAX_PDF_MB = _int_setting("ORION_MAX_PDF_MB", 40)

# Parallel PDF downloads within one research run.
DOWNLOAD_WORKERS = max(1, _int_setting("ORION_DOWNLOAD_WORKERS", 6))

# Research runs executing at the same time. Extra runs wait
# in a queue.
MAX_CONCURRENT_JOBS = max(1, _int_setting("ORION_MAX_CONCURRENT_JOBS", 2))

# Contact email for the Unpaywall API (required by its
# terms). Unpaywall lookups are skipped when unset.
UNPAYWALL_EMAIL = os.getenv("ORION_UNPAYWALL_EMAIL", "").strip()
