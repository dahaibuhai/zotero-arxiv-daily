"""Bounded retries for transient failures while reading the Zotero corpus."""

import re
import time


def retry_transient(operation, on_retry, attempts=4):
    for attempt in range(attempts):
        try:
            return operation()
        except Exception as exc:
            cause = exc
            status = None
            while cause is not None:
                status = getattr(getattr(cause, "response", None), "status_code", None)
                if status is not None:
                    break
                match = re.search(r"Code:\s*(\d{3})", str(cause))
                if match:
                    status = int(match.group(1))
                    break
                cause = cause.__cause__
            if status not in (429, 500, 502, 503, 504) or attempt + 1 >= attempts:
                raise
            delay = min(60, 15 * 2 ** attempt)
            on_retry(status, attempt + 1, attempts, delay)
            time.sleep(delay)
