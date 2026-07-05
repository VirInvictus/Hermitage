"""Entry point for `python -m hermitage` and the `hermitage` console script."""

import signal
import sys


def main():
    # Let Ctrl+C in the terminal exit cleanly instead of spewing GTK errors
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))

    # Register bundled fonts before any widget asks Pango for a face.
    from hermitage.typography import register_bundled_fonts

    register_bundled_fonts()

    from hermitage.app import run

    run()


if __name__ == "__main__":
    main()
