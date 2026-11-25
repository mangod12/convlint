"""Transcript loading: JSON, JSONL, and plain-text 'Agent: ...' formats."""
from __future__ import annotations

import csv
import glob
import json
import os
import re
from typing import Iterable, List, Optional

from .models import AGENT, USER, Transcript, Turn

_AGENT_NAMES = {"agent", "ai", "assistant", "bot", "tutor", "riya", "system-agent"}
_USER_NAMES = {"user", "customer", "learner", "student", "caller", "human", "client"}

_TXT_LINE = re.compile(
    r"^(?:\[(?P<ts>\d{1,2}:\d{2}(?::\d{2})?)\]\s*)?"
    r"(?P<role>[A-Za-z][A-Za-z ._-]{0,20}?)\s*[:|-]\s+"
    r"(?P<text>.+?)\s*$"
)


def normalize_role(role: str) -> str:
    r = role.strip().lower()
    if r in _AGENT_NAMES:
        return AGENT
    if r in _USER_NAMES:
        return USER
    return r


def _ts_to_seconds(ts: str) -> float:
    parts = [int(p) for p in ts.split(":")]
    if len(parts) == 2:
        return float(parts[0] * 60 + parts[1])
    return float(parts[0] * 3600 + parts[1] * 60 + parts[2])


def _turn_from_obj(obj: dict, idx: int) -> Optional[Turn]:
    role = obj.get("role") or obj.get("speaker") or obj.get("from") or ""
    text = obj.get("text") or obj.get("content") or obj.get("message") or ""
    if not role or not isinstance(text, str) or not text.strip():
        return None
    t = obj.get("t", obj.get("timestamp", obj.get("time")))
    tval: Optional[float] = None
    if isinstance(t, (int, float)):
        tval = float(t)
    elif isinstance(t, str):
        ts = t.strip()
        if re.fullmatch(r"\d{1,2}:\d{2}(:\d{2})?", ts):
            tval = _ts_to_seconds(ts)
        else:
            try:
                tval = float(ts)
            except ValueError:
                tval = None
    return Turn(role=normalize_role(str(role)), text=text.strip(), t=tval)


def loads_json(text: str, tid: str) -> Transcript:
    data = json.loads(text)
    if isinstance(data, list):
        meta: dict = {}
        raw_turns = data
    elif isinstance(data, dict):
        meta = dict(data.get("meta") or {})
        for k in ("max_duration_s", "time_limit_s", "call_id", "agent_name", "language"):
            if k in data and k not in meta:
                meta[k] = data[k]
        raw_turns = data.get("turns") or data.get("messages") or data.get("transcript") or []
    else:
        raise ValueError(f"{tid}: unsupported JSON root {type(data).__name__}")
    turns = []
    for i, obj in enumerate(raw_turns):
        if isinstance(obj, dict):
            tr = _turn_from_obj(obj, i)
            if tr:
                turns.append(tr)
    return Transcript(id=tid, turns=turns, meta=meta)


def loads_jsonl(text: str, tid: str) -> Transcript:
    turns = []
    meta: dict = {}
    for i, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        if i == 0 and isinstance(obj, dict) and "meta" in obj and "role" not in obj:
            meta = dict(obj["meta"])
            continue
        if isinstance(obj, dict):
            tr = _turn_from_obj(obj, i)
            if tr:
                turns.append(tr)
    return Transcript(id=tid, turns=turns, meta=meta)


def loads_txt(text: str, tid: str) -> Transcript:
    turns = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        m = _TXT_LINE.match(line)
        if not m:
            continue
        tval = _ts_to_seconds(m.group("ts")) if m.group("ts") else None
        turns.append(Turn(role=normalize_role(m.group("role")), text=m.group("text"), t=tval))
    return Transcript(id=tid, turns=turns)


def loads_csv(text: str, tid: str) -> Transcript:
    rows = list(csv.DictReader(text.splitlines()))
    turns = []
    for i, row in enumerate(rows):
        tr = _turn_from_obj({k.strip().lower(): v for k, v in row.items() if k}, i)
        if tr:
            turns.append(tr)
    return Transcript(id=tid, turns=turns)


def load(path: str) -> Transcript:
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    tid = os.path.splitext(os.path.basename(path))[0]
    ext = os.path.splitext(path)[1].lower()
    if ext == ".jsonl":
        return loads_jsonl(text, tid)
    if ext == ".json":
        return loads_json(text, tid)
    if ext == ".csv":
        return loads_csv(text, tid)
    # sniff
    stripped = text.lstrip()
    if stripped.startswith("{") or stripped.startswith("["):
        try:
            return loads_json(text, tid)
        except (ValueError, json.JSONDecodeError):
            pass
    return loads_txt(text, tid)


def expand_paths(paths: Iterable[str]) -> List[str]:
    out: List[str] = []
    for p in paths:
        if os.path.isdir(p):
            for ext in ("*.json", "*.jsonl", "*.txt", "*.csv"):
                out.extend(glob.glob(os.path.join(p, "**", ext), recursive=True))
        else:
            out.append(p)
    return sorted(dict.fromkeys(out))
