"""``python -m botbase`` — same as the ``botbase`` console script."""

from __future__ import annotations

import sys

from botbase.cli import main

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
