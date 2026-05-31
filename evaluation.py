"""Registre d'évaluation — agrège les jalons par candidat. ÉVALUATEUR uniquement.

Ce module n'est jamais importé par core.py : il vit côté outillage et n'apparaît
donc pas dans le source révélé au candidat.
"""
import threading
import time


class Registry:
    def __init__(self):
        self._data = {}
        self._lock = threading.Lock()

    def record(self, key: str, event: str, detail: str | None = None):
        with self._lock:
            entry = self._data.setdefault(
                key, {"events": [], "failed_attempts": 0, "errors": []}
            )
            entry["events"].append({"event": event, "ts": time.time()})
            if event == "post_token_fail":
                entry["failed_attempts"] += 1
                if detail:
                    entry["errors"].append(detail)

    def report(self) -> dict:
        with self._lock:
            out = {}
            for key, entry in self._data.items():
                events = entry["events"]
                start = next((e["ts"] for e in events if e["event"] == "start"), None)
                final = next((e["ts"] for e in events if e["event"] == "final"), None)
                duration = (
                    round(final - start, 3)
                    if start is not None and final is not None
                    else None
                )
                out[key] = {
                    "events": events,
                    "failed_attempts": entry["failed_attempts"],
                    "errors": entry["errors"],
                    "duration_to_final_seconds": duration,
                }
            return out


registry = Registry()
