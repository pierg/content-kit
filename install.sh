#!/usr/bin/env bash
# Kept for one minor version: the installer is `ckit init` now. This runs the checkout's own
# engine, so `bash install.sh <repo>` vendors from this checkout exactly as before.
#
#   bash install.sh /path/to/repo [--name "Name"] [--port 5180]
exec "$(cd "$(dirname "$0")" && pwd)/bin/ckit" init "$@"
