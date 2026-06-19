# Contributing

Thank you for considering contributing to Clipboard Manager!

## Setup

```bash
git clone https://github.com/aCS6/clipboard-manager
cd clipboard-manager
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 gir1.2-gdkpixbuf-2.0
```

## Running

```bash
make run
```

## Tests

```bash
make test
```

Tests cover the data layer only (`tests/test_storage.py`) — no display required.

## How to contribute

1. Fork the repo and create a branch: `git checkout -b my-fix`
2. Make your change. Run `make test` to verify nothing is broken.
3. Open a pull request with a clear description of what and why.

## Guidelines

- Keep it lightweight — this app runs in the background all day.
- No new Python dependencies beyond stdlib + system `python3-gi`.
- Match the existing code style (no formatter required, just be consistent).
- One logical change per PR.

## Reporting bugs

Open a GitHub Issue with:
- Ubuntu version (`lsb_release -a`)
- GNOME Shell version (`gnome-shell --version`)
- Steps to reproduce
- What you expected vs. what happened
- Terminal output if any

## Future roadmap (good first issues)

- [ ] Publish to PyPI (`make pip-build` + twine upload)
- [ ] Publish to Ubuntu PPA / build `.deb` (`make deb`)
- [ ] Multi-monitor support (popup on active monitor)
- [ ] Global keyboard shortcut (requires GNOME custom keybinding via gsettings)
