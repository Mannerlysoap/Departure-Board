#!/bin/bash
# Start Cage in the background
cage -d firefox &

# Give it a moment to initialize
sleep 2

# Apply the 270-degree rotation (Left side up)
wlr-randr --output HDMI-A-1 --transform 270
