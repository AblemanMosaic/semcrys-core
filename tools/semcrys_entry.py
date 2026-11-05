"""PyInstaller entry point for the standalone Windows CLI."""
import multiprocessing

from semcrys.cli import main


if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())

