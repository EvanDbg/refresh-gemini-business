#!/bin/bash
# Entrypoint script that runs the application with xvfb for virtual display
# This allows running non-headless browser in a headless environment

set -e

# Start Xvfb (virtual framebuffer)
echo "Starting Xvfb virtual display..."
Xvfb :99 -screen 0 1920x1080x24 -nolisten tcp &
export DISPLAY=:99

# Wait for Xvfb to start
sleep 2

# Run the main application with --no-headless flag
echo "Starting Gemini Business Cookie Refresh Tool..."
exec python -m src.main --no-headless "$@"
