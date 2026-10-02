#!/usr/bin/env sh
# Install md2dstu as a command by linking the launcher into a bin directory.
#
#   ./install.sh               link into ~/.local/bin (or $BIN_DIR)
#   ./install.sh --uninstall   remove the links
#
# Also links skills/md2dstu into the skill directory of every AI agent whose
# config directory exists: Claude Code, Codex, Cursor, Gemini CLI, Antigravity,
# opencode.
#
# The checkout must stay in place: the launcher finds filters/, templates/
# and resources/ next to its real path, so `git pull` updates the command.

set -eu

REPO_DIR=$(cd "$(dirname "$0")" && pwd -P)
BIN_DIR=${BIN_DIR:-"$HOME/.local/bin"}
TARGET="$BIN_DIR/md2dstu"
SKILL_SRC="$REPO_DIR/skills/md2dstu"

# Lines of "<agent config dir> <skill dir>"; a skill is linked only when the
# agent's config dir exists.
skill_dirs() {
    cat <<EOF
$HOME/.claude $HOME/.claude/skills
${CODEX_HOME:-$HOME/.codex} $HOME/.agents/skills
$HOME/.cursor $HOME/.cursor/skills
$HOME/.gemini $HOME/.gemini/skills
$HOME/.gemini $HOME/.gemini/config/skills
${XDG_CONFIG_HOME:-$HOME/.config}/opencode ${XDG_CONFIG_HOME:-$HOME/.config}/opencode/skills
EOF
}

if [ "${1:-}" = "--uninstall" ]; then
    if [ -L "$TARGET" ]; then
        rm "$TARGET"
        echo "Removed $TARGET"
    else
        echo "Nothing to remove: $TARGET is not a symlink"
    fi
    skill_dirs | while read -r _ dir; do
        if [ "$(readlink "$dir/md2dstu" 2>/dev/null)" = "$SKILL_SRC" ]; then
            rm "$dir/md2dstu"
            echo "Removed skill $dir/md2dstu"
        fi
    done
    exit 0
fi

# Dependencies
missing=0
if ! command -v python3 >/dev/null 2>&1 ||
    ! python3 -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
    echo "error: Python 3.10+ is required" >&2
    missing=1
fi
if ! command -v pandoc >/dev/null 2>&1; then
    echo "error: pandoc 3.x is required (https://pandoc.org/installing.html)" >&2
    missing=1
elif ! pandoc --version | head -n 1 | grep -q '^pandoc 3\.'; then
    echo "warning: pandoc 3.x expected, found: $(pandoc --version | head -n 1)" >&2
fi
if ! command -v libreoffice >/dev/null 2>&1 && ! command -v soffice >/dev/null 2>&1; then
    echo "note: LibreOffice not found; .doc/.odt output and TOC page numbers are unavailable"
fi
[ "$missing" -eq 0 ] || exit 1

# Link
mkdir -p "$BIN_DIR"
if [ -e "$TARGET" ] && [ ! -L "$TARGET" ]; then
    echo "error: $TARGET exists and is not a symlink; remove it first" >&2
    exit 1
fi
ln -sfn "$REPO_DIR/md2dstu" "$TARGET"
echo "Linked $TARGET -> $REPO_DIR/md2dstu"

# PATH
case ":$PATH:" in
*":$BIN_DIR:"*) ;;
*)
    rc="$HOME/.bashrc"
    [ "${SHELL##*/}" = "zsh" ] && rc="$HOME/.zshrc"
    line="export PATH=\"$BIN_DIR:\$PATH\""
    if ! grep -qsF "$line" "$rc"; then
        printf '\n# md2dstu\n%s\n' "$line" >>"$rc"
        echo "Added $BIN_DIR to PATH in $rc"
    fi
    echo "Open a new terminal or run: . $rc"
    ;;
esac

# AI agent skill
skill_dirs | while read -r home dir; do
    [ -d "$home" ] || continue
    if [ -e "$dir/md2dstu" ] && [ ! -L "$dir/md2dstu" ]; then
        echo "warning: $dir/md2dstu exists and is not a symlink; skill not linked" >&2
        continue
    fi
    mkdir -p "$dir"
    ln -sfn "$SKILL_SRC" "$dir/md2dstu"
    echo "Linked skill $dir/md2dstu"
done

"$TARGET" --help >/dev/null && echo "Done: md2dstu is installed"
