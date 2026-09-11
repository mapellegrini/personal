#!/usr/bin/env bash

# To manually clone the repo to /srv:
# git clone https://github.com/mapellegrini/personal.git /srv/personal

set -euo pipefail

REPO_URL="https://github.com/mapellegrini/personal.git"
REPO_DIR="/srv/personal"

ETC_SOURCE="${REPO_DIR}/server/etc"
ALIASES_SOURCE="${REPO_DIR}/server/homedir/.bash_aliases"
ROOT_BIN="${REPO_DIR}/server/root_bin"

###############################################################################
# Help
###############################################################################

usage() {
    cat <<EOF
Usage: $(basename "$0") [OPTION]

Install the personal server configuration.

This script:

  1. Clones the personal repository to ${REPO_DIR} if it is not already there.
  2. Makes the repository readable/traversable by all users.
  3. Symlinks files under server/etc into their corresponding locations
     under /etc.
  4. Symlinks server/homedir/.bash_aliases to:
       /home/mark/.bash_aliases
       /root/.bash_aliases
  5. Adds server/root_bin to root's PATH in /root/.bashrc.

Existing regular files and symlinks managed by step 3 are replaced.
Existing real directories are never replaced.

The script does NOT automatically update an existing Git checkout.

To update an existing installation:

  cd ${REPO_DIR}
  git pull --ff-only
  sudo ./server/install.sh

Options:
  -h, --help    Show this help message and exit.

The installation portion of this script must be run as root.
EOF
}

case "${1:-}" in
    -h|--help)
        usage
        exit 0
        ;;
    "")
        ;;
    *)
        echo "ERROR: Unknown option: $1" >&2
        echo >&2
        usage >&2
        exit 2
        ;;
esac

###############################################################################
# Must be run as root
###############################################################################

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run as root." >&2
    echo "Try: sudo $0" >&2
    exit 1
fi

###############################################################################
# 1. Clone repository to /srv if it is not already present
#
# This script intentionally does NOT update an existing checkout.
#
# To update the repository:
#
#   cd /srv/personal
#   git pull --ff-only
#   sudo ./server/install.sh
###############################################################################

if [[ -d "${REPO_DIR}/.git" ]]; then
    echo "Repository already exists at ${REPO_DIR}."
    echo "Using the currently checked-out version."
elif [[ -e "${REPO_DIR}" ]]; then
    echo "ERROR: ${REPO_DIR} already exists but is not a Git repository." >&2
    exit 1
else
    echo "Cloning repository..."
    git clone "${REPO_URL}" "${REPO_DIR}"
fi

###############################################################################
# 2. Make repository readable/traversable by all users
###############################################################################

echo "Making repository readable by all users..."
chmod -R a+rX "${REPO_DIR}"

###############################################################################
# 3. Symlink files under server/etc into /etc
#
# Examples:
#
#   server/etc/hosts
#       -> /etc/hosts
#
#   server/etc/samba/smb.conf
#       -> /etc/samba/smb.conf
#
#   server/etc/cron.daily/foo
#       -> /etc/cron.daily/foo
#
# Existing destination files or symlinks are replaced.
# Existing real directories are never replaced.
###############################################################################

echo "Installing /etc symlinks..."

while IFS= read -r -d '' source; do
    relative="${source#"${ETC_SOURCE}/"}"
    destination="/etc/${relative}"
    destination_dir="$(dirname "${destination}")"

    mkdir -p "${destination_dir}"

    # Never replace a real directory with a symlink.
    if [[ -d "${destination}" && ! -L "${destination}" ]]; then
        echo "ERROR: ${destination} is a directory; refusing to replace it." >&2
        exit 1
    fi

    echo "  ${destination} -> ${source}"

    ln -sfn "${source}" "${destination}"
done < <(find "${ETC_SOURCE}" -type f -print0)

###############################################################################
# 4. Install .bash_aliases for mark and root
###############################################################################

echo "Installing .bash_aliases..."

if [[ ! -d /home/mark ]]; then
    echo "ERROR: /home/mark does not exist." >&2
    exit 1
fi

ln -sfn "${ALIASES_SOURCE}" /home/mark/.bash_aliases
ln -sfn "${ALIASES_SOURCE}" /root/.bash_aliases

###############################################################################
# 5. Add server/root_bin to root's PATH
#
# Idempotent: only add it if the exact PATH line isn't already present
# in /root/.bashrc.
###############################################################################

echo "Configuring root PATH..."

ROOT_BASHRC="/root/.bashrc"
PATH_LINE='export PATH="/srv/personal/server/root_bin:$PATH"'

touch "${ROOT_BASHRC}"

if ! grep -Fqx "${PATH_LINE}" "${ROOT_BASHRC}"; then
    {
        echo
        echo '# Personal server utilities'
        echo "${PATH_LINE}"
    } >> "${ROOT_BASHRC}"

    echo "  Added ${ROOT_BIN} to root's PATH."
else
    echo "  ${ROOT_BIN} is already configured in root's PATH."
fi

###############################################################################
# Complete
###############################################################################

echo
echo "Installation complete."
echo
echo "Repository: ${REPO_DIR}"
echo
echo "Aliases:"
echo "  /home/mark/.bash_aliases -> ${ALIASES_SOURCE}"
echo "  /root/.bash_aliases      -> ${ALIASES_SOURCE}"
echo
echo "Root binaries:"
echo "  ${ROOT_BIN}"
echo
echo "To update this server configuration later:"
echo "  cd ${REPO_DIR}"
echo "  git pull --ff-only"
echo "  sudo ./server/install.sh"
echo
echo "Start a new root shell, or run:"
echo "  source /root/.bashrc"
