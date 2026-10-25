from app.core import MAX_ITEMS


class Item:
    def __init__(self, name):
        self.name = name[:MAX_ITEMS]
