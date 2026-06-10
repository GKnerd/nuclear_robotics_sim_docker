#!/bin/bash
# macOS has no native X server, so unlike the Linux image we cannot forward
# windows to the host. Instead we run a virtual desktop entirely inside the
# container and stream it to the browser:
#
#   GUI app (rviz2 / mujoco viewer)  -> draws to Xvfb (a framebuffer in RAM)
#   x11vnc                           -> shares that framebuffer over VNC (5900)
#   websockify / noVNC               -> exposes it to a browser    (http 6080)
#
# All OpenGL is software-rendered via Mesa/llvmpipe (no GPU passthrough on Mac).
# After the GUI stack is up we hand off to the stock ROS entrypoint so the
# interactive shell behaves exactly like the Linux image.
set -e

export DISPLAY="${DISPLAY:-:1}"
GUI_RES="${GUI_RESOLUTION:-1920x1080x24}"
VNC_PORT="${VNC_PORT:-5900}"
NOVNC_PORT="${NOVNC_PORT:-6080}"

# Clear any stale X lock left behind by a previous run on the same display.
rm -f "/tmp/.X${DISPLAY#:}-lock" "/tmp/.X11-unix/X${DISPLAY#:}" 2>/dev/null || true

# 1) Virtual framebuffer X server: the "screen" that exists only in RAM.
Xvfb "$DISPLAY" -screen 0 "$GUI_RES" -ac +extension GLX +render -noreset &

# Wait until the X server is actually accepting connections before launching
# anything that needs it.
for _ in $(seq 1 30); do
    if xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; then break; fi
    sleep 0.3
done

# 2) Minimal window manager so windows have title bars and can be moved/resized.
openbox &

# 3) VNC server streaming the Xvfb framebuffer. No password: it is only
#    reachable through the ports you explicitly publish from the container.
x11vnc -display "$DISPLAY" -forever -shared -nopw -rfbport "$VNC_PORT" \
       -bg -o /tmp/x11vnc.log

# 4) noVNC browser front-end (websockify wraps the VNC stream in WebSockets).
websockify --web=/usr/share/novnc "$NOVNC_PORT" "localhost:$VNC_PORT" \
       >/tmp/novnc.log 2>&1 &

echo "============================================================"
echo " Virtual desktop ready:"
echo "   Browser : http://localhost:${NOVNC_PORT}/vnc.html"
echo "   VNC     : localhost:${VNC_PORT}  (e.g. macOS Screen Sharing)"
echo "============================================================"

# Hand off to the stock ROS entrypoint (sources ROS + the workspace), then CMD.
exec /ros_entrypoint.sh "$@"
