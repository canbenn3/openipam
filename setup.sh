#!/usr/bin/env bash
set -e

echo "🚀 Starting DHCP-IPAM setup with pyenv..."

WORKDIR="/opt/dhcp-ipam"
PYDHCLIB_PATH="$WORKDIR/openIPAM/pydhcplib"

# --- Ensure root for package installation ---
if [[ "$EUID" -ne 0 ]]; then
  echo "❌ Please run this script as root (sudo)."
  exit 1
fi

# --- Install dependencies for pyenv and build tools ---
echo "🧰 Installing system dependencies..."
apt update
apt install -y \
    build-essential \
    curl \
    git \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    wget \
    llvm \
    libncurses-dev \
    xz-utils \
    tk-dev \
    libffi-dev \
    liblzma-dev \
    libpq-dev \
    libldap2-dev \
    libsasl2-dev \
    sudo

# --- Install pyenv for current user (not root) ---
USER_HOME="/home/bennett"
echo "🐍 Installing pyenv for user 'bennett'..."
if [[ ! -d "$USER_HOME/.pyenv" ]]; then
    sudo -u bennett -H bash -c "curl https://pyenv.run | bash"
fi

sudo -u bennett -H bash -c '
export PYENV_ROOT="$HOME/.pyenv"
export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init --path)"
eval "$(pyenv init -)"
pyenv install -s 3.7.3
pyenv local 3.7.3
python -m pip install --upgrade pip setuptools
pip install -r ~/dhcp-ipam/requirements.txt
pip install -e ~/dhcp-ipam/openIPAM/pydhcplib
'

# --- Finish ---
echo "✅ Setup complete!"
echo "You can run the DHCP server using:"
echo "  cd $WORKDIR && python openIPAM/openipam_dhcpd"
