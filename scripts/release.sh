#!/usr/bin/env bash
# Umbrella build/release script for the Langrisser V (PS1) English patch.
#
# The patch is a binary diff against the original game image, so the build
# needs the verified original BIN in iso/ (never committed). A given clean
# commit always produces a byte-identical PPF, so builds are reproducible
# per-commit; --release refuses a dirty tree to keep that guarantee.
#
#   scripts/release.sh                 # build dev artifacts into dist/
#   scripts/release.sh -v 1.1          # set the version label explicitly
#   scripts/release.sh --release       # clean-tree build, version from git tag
#
# On an exact git tag (v1, v1.1, ...) the version defaults to the tag without
# the leading "v"; otherwise it defaults to "dev".
set -euo pipefail

cd "$(dirname "$0")/.."

PYTHON="${PYTHON:-python3}"
ORIG_BIN="${ORIG_BIN:-iso/SLPS-01818-9-B.bin}"
ORIG_SHA256="${ORIG_SHA256:-af3f5e1d6912f31f712d43cf71d954481fa9814021e62b41fdd8fce0c9429247}"
EXTRACT_DIR="work/extracted"
DIST="dist"
PPF="patches/langrisser_v_en.ppf"
PATCHED_BIN="work/build/langrisser_v_en.bin"

VERSION=""
RELEASE=0

usage() { sed -n '2,15p' "$0" | sed 's/^# \{0,1\}//'; }

while [[ $# -gt 0 ]]; do
	case "$1" in
		-v|--version) VERSION="${2:?--version needs an argument}"; shift 2 ;;
		--release)    RELEASE=1; shift ;;
		-h|--help)    usage; exit 0 ;;
		*) echo "unknown argument: $1" >&2; usage; exit 1 ;;
	esac
done

if [[ -z "$VERSION" ]]; then
	tag="$(git describe --tags --exact-match 2>/dev/null || true)"
	if [[ -n "$tag" ]]; then VERSION="${tag#v}"; else VERSION="dev"; fi
fi

log() { printf '\n==> %s\n' "$*"; }

if [[ "$RELEASE" == 1 && -n "$(git status --porcelain)" ]]; then
	echo "ERROR: working tree is dirty; a release build must be clean so the" >&2
	echo "commit hash baked into the title screen matches the artifacts." >&2
	git status --short >&2
	exit 1
fi

if [[ ! -f "$ORIG_BIN" ]]; then
	echo "ERROR: original image not found at $ORIG_BIN." >&2
	echo "Place the verified Langrisser V PS1 BIN there (see README)." >&2
	exit 1
fi

log "Verifying original image"
echo "$ORIG_SHA256  $ORIG_BIN" | sha256sum -c -

if [[ ! -f "$EXTRACT_DIR/SCEN.DAT" ]]; then
	log "Extracting game files"
	mkdir -p "$EXTRACT_DIR"
	for spec in \
		"/L5/SCEN.DAT:SCEN.DAT" \
		"/L5/SCEN2.DAT:SCEN2.DAT" \
		"/L5/SYSTEM.BIN:SYSTEM.BIN" \
		"/L5/IMG.DAT:IMG.DAT" \
		"/SLPS_018.19:SLPS_018.19"; do
		"$PYTHON" scripts/iso_mode2.py "$ORIG_BIN" extract "${spec%%:*}" "$EXTRACT_DIR/${spec##*:}"
	done
fi

log "Building patch (version $VERSION)"
"$PYTHON" scripts/lang5_build_ppf.py --patch-version "$VERSION" --out-ppf "$PPF"

log "Assembling $DIST/"
mkdir -p "$DIST"
# "v" prefix only for numeric versions (v1.1); leave labels like "dev" as-is.
if [[ "$VERSION" =~ ^[0-9] ]]; then label="v$VERSION"; else label="$VERSION"; fi
ppf_name="langrisser_v_en-$label.ppf"
cp "$PPF" "$DIST/$ppf_name"

ppf_sha="$(sha256sum "$DIST/$ppf_name" | cut -d' ' -f1)"
img_sha="$(sha256sum "$PATCHED_BIN" | cut -d' ' -f1)"
img_md5="$(md5sum "$PATCHED_BIN" | cut -d' ' -f1)"
img_sz="$(stat -c%s "$PATCHED_BIN")"

# Canonical "sha256sum -c" file: one checkable line for the distributed PPF,
# the rest as "#" comments (ignored by sha256sum -c, informative for people).
cat > "$DIST/SHA256SUMS" <<EOF
# Langrisser V (PS1) English translation - $label
# commit $(git rev-parse HEAD)
$ppf_sha  $ppf_name
#
# Patched image (apply this PPF to the verified original BIN):
#   sha256 $img_sha
#   md5    $img_md5
#   size   $img_sz bytes
# Required original SLPS-01818-9-B.bin (the .cue is unchanged):
#   sha256 $ORIG_SHA256
EOF

log "Release artifacts in $DIST/:"
ls -1 "$DIST"
