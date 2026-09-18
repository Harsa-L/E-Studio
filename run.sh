#!/bin/bash

# 1. Install missing system, GUI, and keyboard dependencies for Ubuntu 24.04
if ! command -v pcmanfm-qt &> /dev/null; then
    echo "📦 Installing missing system dependencies and PCManFM-Qt..."
    sudo apt-get update && sudo apt-get install -y \
        xvfb x11vnc fluxbox novnc python3-websockify \
        pcmanfm-qt \
        libgl1 libglib2.0-0 libxcb-cursor0 \
        libxkbcommon0 libxkbcommon-x11-0 libxcb-icccm4 \
        libxcb-image0 libxcb-keysyms1 libxcb-randr0 \
        libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 \
        libxcb-xfixes0 libegl1 libfontconfig1 libxrender1
else
    echo "✅ All system dependencies and PCManFM-Qt are met."
fi

# 2. Setup the virtual display port
export DISPLAY=:1

# 3. Force Qt apps (like PCManFM-Qt and your app) to auto-scale on High-DPI screens
export QT_AUTO_SCREEN_SCALE_FACTOR=1
export QT_SCALE_FACTOR=1.2 # Adjust this number (e.g., 1.5) if you want things even larger!

# 4. Kill any previously hanging GUI processes to prevent port conflicts
echo "🧹 Cleaning up old display instances..."
pkill -f Xvfb
pkill -f x11vnc
pkill -f fluxbox
pkill -f websockify
pkill -f pcmanfm-qt
sleep 1

# 5. Spin up the Virtual Display and Window Manager in the background
echo "🖥️  Starting virtual frame buffer (Xvfb) with enhanced DPI sizing..."
Xvfb :1 -screen 0 1280x720x24 -dpi 120 &
sleep 1

echo "🪟 Starting window manager (Fluxbox)..."
fluxbox &
sleep 1

echo "📡 Starting VNC streamer (x11vnc)..."
x11vnc -display :1 -nopw -listen localhost -xkb &
sleep 1

echo "🌐 Launching noVNC Web Server on Port 6080..."
websockify --web=/usr/share/novnc/ 6080 localhost:5900 &
sleep 2

# 6. Open PCManFM-Qt in the background focused on your workspace directory
echo "📂 Spawning PCManFM-Qt File Explorer..."
pcmanfm-qt /workspaces/E-Studio &
sleep 1

# 7. Activate Python Environment and Launch your app
echo "🚀 Activating virtual environment and launching app.py..."
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

python main.py
