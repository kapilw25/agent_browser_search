#!/bin/bash

# Create screenshots directory if it doesn't exist
mkdir -p screenshots

# Ensure the script is executable
chmod +x test4_browser_use_screenshot.py

# Activate the virtual environment
source venv_browser/bin/activate

# Run the Streamlit app with xvfb-run
xvfb-run -a streamlit run test4_browser_use_screenshot.py --server.port 8501 --server.address 0.0.0.0
