#!/bin/bash
export LD_PRELOAD="/nix/store/92nrp8f5bcyxy57w30wxj5ncvygz1wnx-xcb-util-cursor-0.1.5/lib/libxcb-cursor.so.0:$LD_PRELOAD"
export LD_LIBRARY_PATH="/nix/store/92nrp8f5bcyxy57w30wxj5ncvygz1wnx-xcb-util-cursor-0.1.5/lib:$LD_LIBRARY_PATH"
export DISPLAY="${DISPLAY:-:0}"
export QT_XCB_NO_XI2=1
exec python main.py "$@"
