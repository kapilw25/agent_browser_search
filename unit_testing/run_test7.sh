#!/bin/bash

# Activate the virtual environment
source venv_browser/bin/activate

# Run the Streamlit app with xvfb-run
xvfb-run -a streamlit run test7_fragment_output.py --server.port 8501 --server.address 0.0.0.0
