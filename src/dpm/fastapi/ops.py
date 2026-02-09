from __future__ import annotations

from typing import Protocol

from jinja2_fragments.fastapi import Jinja2Blocks


class ServerOps(Protocol):
    templates: Jinja2Blocks
