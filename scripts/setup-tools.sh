#!/usr/bin/env bash
# Clones the music-production tools into tools/ (git-ignored) at pinned commits.
# Re-runnable: existing, healthy clones are skipped unless --force is passed.
#
#   ./scripts/setup-tools.sh            # install missing tools
#   ./scripts/setup-tools.sh --force    # re-clone everything
#
# NOTE: these are third-party repositories. They are NOT tracked by this repo
# (see .gitignore) and each keeps its own license and .git directory.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TOOLS="$ROOT/tools"
FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

# dir|url|commit|branch|--depth 1 or empty
PINNED=(
  "strudel-claude|https://github.com/renatoworks/strudel-claude.git|a62f4f0d731f54308092334f438992dff5b56876|main|"
  "claude-ai-music-skills|https://github.com/bitwize-music-studio/claude-ai-music-skills.git|597d928fb2c8316ee13159771405813174aa01de|main|"
  "aimusicmixer|https://github.com/EnriqueJRZ/aimusicmixer-backend.git|77b090b7f899e7781d9bcbea85c80d44640d7295|main|"
  "stem-separator|https://github.com/Su1ph3r/stem-separator.git|286b5577b6655ad07ca2d2e0d32d96ccb653190d|main|"
  "StemForge|https://github.com/tsondo/StemForge.git|3bdff55d8a0aa0963624167f4881805df4736e1a|main|"
  # Upstream history is ~1.5 GB, so this one is pinned shallow.
  "AI-Beat-Maker|https://github.com/guyyariv/AI-Beat-Maker.git|b550b71ee7b136f75dbed4de5116aa89e80b9ddf|master|--depth 1"
  "audiocraft|https://github.com/facebookresearch/audiocraft.git|896ec7c47f5e5d1e5aa1e4b260c4405328bf009d|main|"
)

mkdir -p "$TOOLS"

for entry in "${PINNED[@]}"; do
  IFS='|' read -r name url commit branch depth <<< "$entry"
  dest="$TOOLS/$name"

  if [[ -d "$dest/.git" && $FORCE -eq 0 ]]; then
    echo "✓ $name already present — skipping (use --force to re-clone)"
    continue
  fi

  if [[ -e "$dest" ]]; then
    echo "→ removing existing $name"
    rm -rf "$dest"
  fi

  echo "↓ cloning $name"
  git clone --quiet ${depth:+$depth} --branch "$branch" "$url" "$dest"
  git -C "$dest" checkout --quiet "$commit"
  echo "  pinned at $(git -C "$dest" rev-parse --short HEAD) ($(du -sh "$dest" | cut -f1))"
done

echo
echo "Done. tools/ is git-ignored; nothing to commit."
