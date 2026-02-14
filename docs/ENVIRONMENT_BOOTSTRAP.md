# Environment Bootstrap

Use this when the environment is reset and commands start failing with
`command not found`.

## One-shot restore

```bash
./scripts/bootstrap_env.sh
```

This script installs/reinstalls the core tooling used by this project:

- CLI/utilities:
  - `curl`, `unzip`, `unar`, `unrar-free`, `xxd`, `ripgrep`
  - `cmake`, `ninja-build`, `build-essential`, `pkg-config`
  - `iproute2`, `net-tools`
- Reverse tools:
  - `php-cli`, `binwalk`, `binutils-mipsel-linux-gnu`
  - `mednafen` (runtime verification support)
  - `gdb`, `gdb-multiarch`
  - `xvfb`, `xdotool`, `openbox`
- OCR/fonts:
  - `tesseract-ocr`, `tesseract-ocr-jpn`, `fonts-noto-cjk`
- Python runtime/deps:
  - `python3`, `python3-pip`, `python3-capstone`
  - pip: `pillow`, `numpy`

## Notes

- Script is idempotent and safe to re-run.
- It uses `sudo apt-get` and `sudo python3 -m pip`.
- `translation.txt` is intentionally not tracked by git.
