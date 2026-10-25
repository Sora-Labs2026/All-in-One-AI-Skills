import argparse
import os

from . import core
from .models import Item


def main():
    parser = argparse.ArgumentParser()
    parser.parse_args()
    return core.run(Item(os.sep))


if __name__ == "__main__":
    main()
