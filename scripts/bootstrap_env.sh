#!/usr/bin/env bash
set -euo pipefail

# Reinstall core tooling for this workspace after environment reset.
# Safe to run multiple times.

APT_PACKAGES=(
  python3
  python3-pip
  python3-capstone
  php-cli
  curl
  unzip
  unar
  unrar-free
  binwalk
  xxd
  ripgrep
  cmake
  ninja-build
  build-essential
  pkg-config
  binutils-mipsel-linux-gnu
  mednafen
  tesseract-ocr
  tesseract-ocr-jpn
  fonts-noto-cjk
)

echo "[*] apt-get update"
sudo apt-get update -y
echo "[*] apt-get install: ${APT_PACKAGES[*]}"
sudo apt-get install -y "${APT_PACKAGES[@]}"

echo "[*] pip install (system python): pillow numpy"
sudo -H python3 -m pip install --quiet --disable-pip-version-check pillow numpy

echo "[*] Done."
echo "Quick checks:"
echo "  python3: $(python3 -V 2>/dev/null || true)"
echo "  rg: $(rg --version 2>/dev/null | head -n1 || true)"
echo "  tesseract: $(tesseract --version 2>/dev/null | head -n1 || true)"
echo "  php: $(php -v 2>/dev/null | head -n1 || true)"
