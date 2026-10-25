from __future__ import annotations

from typing import TYPE_CHECKING

import requests

from app import util

if TYPE_CHECKING:
    from app.models import Item

MAX_ITEMS = 10


class Runner:
    def go(self):
        return util.helper()


def run(item: "Item"):
    from app import heavy  # lazy import: not a cycle edge
    return heavy.compute(item), requests


async def fetch():
    return None
