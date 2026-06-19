"""Entry point — ensures GDK_BACKEND=x11 before any GTK import (per §3.4)."""
import os
import sys


def main() -> None:
    if os.environ.get("GDK_BACKEND") != "x11":
        os.environ["GDK_BACKEND"] = "x11"

    from clipboard_manager.app import ClipboardManagerApp
    app = ClipboardManagerApp()
    sys.exit(app.run(sys.argv))


if __name__ == "__main__":
    main()
