.PHONY: run test install uninstall deb pip-build clean

# Run the app
run:
	GDK_BACKEND=x11 python3 -m clipboard_manager

# Run headless watcher (no UI)
watch:
	GDK_BACKEND=x11 python3 -m clipboard_manager.watcher

# Run tests (no display needed)
test:
	python3 -m pytest tests/ -v

# Install system dependencies (Ubuntu 24.04)
deps:
	sudo apt install -y python3-gi gir1.2-gtk-3.0 \
		gir1.2-ayatanaappindicator3-0.1 gir1.2-gdkpixbuf-2.0

# Install via pip (editable/dev mode)
install:
	pip install --break-system-packages -e .

# Uninstall pip install
uninstall:
	pip uninstall -y clipboard-manager

# Build pip-publishable dist (wheel + sdist)
pip-build:
	python3 -m build
	@echo "Upload with: python3 -m twine upload dist/*"

# Build .deb package → packages/
deb:
	sudo apt install -y debhelper dh-python python3-all pybuild-plugin-pyproject python3-setuptools
	dpkg-buildpackage -us -uc -b
	mkdir -p packages
	mv ../clipboard-manager_*.deb packages/
	@echo "Built: packages/clipboard-manager_*.deb"
	@echo "Install with: sudo dpkg -i packages/clipboard-manager_*.deb"

# Enable autostart for current user
autostart-enable:
	cp packaging/clipboard-manager.desktop ~/.config/autostart/

autostart-disable:
	rm -f ~/.config/autostart/clipboard-manager.desktop

# Install systemd user service
service-install:
	cp packaging/clipboard-manager.service ~/.config/systemd/user/
	systemctl --user daemon-reload
	systemctl --user enable --now clipboard-manager

service-uninstall:
	systemctl --user disable --now clipboard-manager 2>/dev/null || true
	rm -f ~/.config/systemd/user/clipboard-manager.service
	systemctl --user daemon-reload

# Remove all user data
purge:
	rm -rf ~/.local/share/clipboard-manager ~/.config/clipboard-manager
	rm -f ~/.config/autostart/clipboard-manager.desktop

clean:
	rm -rf dist/ build/ *.egg-info __pycache__ .pytest_cache
	find . -name '*.pyc' -delete
