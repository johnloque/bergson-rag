"""Deterministic repair of the faithfulness judge's raw replies, before RAGAS
parses them (`_RepairingJudgeLLM`, `src/generation/faithfulness.py`).

Only the malformations observed on the local judge are repaired, never a
guess at intent (`eval/results/raw_judge_replies_default_20261009.json`, the
judge baseline's three deterministic parse failures):

- a missing comma between two values that sit on separate lines, e.g. two
  claims of one segment (`"…Aristote."` newline `"Il cite…"`), or a
  `"statement"` field followed directly by `"reason"`;
- `\\'`, an escape JSON doesn't have, closing a quoted title
  (`\\"De l'évolution de la vie.\\'`).

A repair is kept only if it turns invalid JSON into valid JSON; a reply that
already parses is never touched, so a well-formed reply reaches RAGAS
byte-for-byte as before.

RAGAS's own retry (`FixOutputFormat`) asks the judge to fix its reply and
expects the fix wrapped as `{"text": "<fixed reply>"}`; the local judge
returns the fixed reply bare, so the retry never succeeded.
`wrap_fix_reply` restores the expected envelope.
"""

from __future__ import annotations

import json
import re

from ragas.prompt.utils import extract_json

# A string's closing quote, then a line break, then the next value's opening
# quote, with no comma in between. A JSON string can't contain a raw line
# break, so this can only match between two tokens.
_MISSING_COMMA = re.compile(r'"([ \t]*\r?\n\s*)(?=["{\[])')
# `\'` not itself escaped (an even run of backslashes before it).
_ESCAPED_APOSTROPHE = re.compile(r"(?<!\\)((?:\\\\)*)\\'")


def _parses(text: str) -> bool:
    try:
        json.loads(extract_json(text))
    except ValueError:
        return False
    return True


def repair_json_reply(text: str) -> str:
    """`text` with the known malformations repaired, if that makes it valid
    JSON; `text` unchanged otherwise (valid already, or beyond repair)."""
    if _parses(text):
        return text
    repaired = _ESCAPED_APOSTROPHE.sub(r"\1'", _MISSING_COMMA.sub(r'",\1', text))
    return repaired if _parses(repaired) else text


def wrap_fix_reply(text: str) -> str:
    """A `FixOutputFormat` reply in its `{"text": ...}` envelope: wrapped if
    the judge returned the fixed JSON bare, unchanged if already wrapped or
    not JSON at all (RAGAS then fails it as before)."""
    try:
        value = json.loads(extract_json(text))
    except ValueError:
        return text
    if isinstance(value, dict) and set(value) == {"text"} and isinstance(value["text"], str):
        return text
    return json.dumps({"text": json.dumps(value, ensure_ascii=False)}, ensure_ascii=False)
