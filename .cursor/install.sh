#!/usr/bin/env bash
# Idempotent repository bootstrap for the Focal Prompt Python project.
set -euo pipefail

# The default image ships Python 3.12 but may lack the venv/ensurepip module.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update
  sudo apt-get install -y python3-venv
fi

# Create the virtualenv once; reuse it on subsequent runs.
if [ ! -x "venv/bin/python" ]; then
  python3 -m venv venv
fi

# shellcheck disable=SC1091
source venv/bin/activate

python -m pip install --upgrade pip
pip install -r requirements.txt
# Editable install exposes the `focalprompt` CLI entrypoint.
pip install -e .
