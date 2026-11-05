#!/bin/bash
# Start the Waveform-Editor GUI on the unix socket ~/.waveform-editor.sock, to be
# reached through an SSH forward from a laptop (see windows/README.txt).
# Usage: start-gui-socket.sh [LOCAL_PORT] [other "waveform-editor gui" options]
LOCAL_PORT=${1:-5006}
shift
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/env.sh" > /dev/null 2>&1
exec waveform-editor gui --socket --local-port "$LOCAL_PORT" "$@"
