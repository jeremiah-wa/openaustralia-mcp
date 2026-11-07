"""PROTOTYPE check: are two snapshots the same once each description is cleaned as Python 3.13 cleans docstrings?"""

import inspect
import json
import sys
from pathlib import Path


def cleaned(path: str) -> dict:
    snapshot = json.loads(Path(path).read_text(encoding="utf-8"))
    for tool in snapshot["tools"]:
        # 3.13 keeps the line break before the closing quotes; cleandoc drops it, so compare without it on both sides.
        tool["description"] = inspect.cleandoc(tool["description"]).rstrip()
    return snapshot


for first, second in zip(sys.argv[1::2], sys.argv[2::2]):
    same = cleaned(first) == cleaned(second)
    print(f"{first} vs {second}: identical once descriptions are cleaned: {same}")
