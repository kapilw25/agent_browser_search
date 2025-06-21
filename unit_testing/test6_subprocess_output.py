import streamlit as st
import subprocess
import os
import time
import threading
import asyncio
from dotenv import load_dotenv
load_dotenv()

# Configure Streamlit page
st.set_page_config(
    page_title="Subprocess Output Test", 
    page_icon="📋",
    layout="wide"
)

st.title("📋 Subprocess Output Streaming Test")
st.markdown("### Testing real-time terminal output streaming using subprocess")

# Create a simple Python script that generates output over time
def create_test_script():
    script_path = "temp_output_script.py"
    with open(script_path, "w") as f:
        f.write("""
import time
import sys
import random

# Print with flush to ensure output is sent immediately
def print_flush(text):
    print(text)
    sys.stdout.flush()

# Generate some output over time
print_flush("Starting test script...")
print_flush("This output should appear in the Streamlit interface in real-time")

# Simulate a process that generates output over time
for i in range(1, 21):
    print_flush(f"Step {i}/20: Processing...")
    
    # Add some random delays to simulate real work
    delay = random.uniform(0.2, 1.0)
    time.sleep(delay)
    
    # Add some variety to the output
    if i % 5 == 0:
        print_flush(f"✅ Milestone reached: {i*5}% complete")
    
    if i % 3 == 0:
        print_flush(f"📊 Status update: Processing data batch {i}")
    
    if i % 7 == 0:
        print_flush(f"🔍 Analyzing results from step {i}")

print_flush("✅ Test script completed successfully!")
""")
    return script_path

# Function to run a subprocess and stream its output to Streamlit
def run_subprocess_with_output_streaming(output_area):
    # Create the test script
    script_path = create_test_script()
    
    try:
        # Run the script as a subprocess
        process = subprocess.Popen(
            ["python", script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Initialize output collection
        all_output = []
        
        # Stream output in real-time
        while True:
            # Read a line from stdout
            output = process.stdout.readline()
            
            # If the process has finished and there's no more output, break
            if output == '' and process.poll() is not None:
                break
            
            # If there's output, display it
            if output:
                all_output.append(output.strip())
                with output_area:
                    st.code("\n".join(all_output))
            
            # Check for errors
            error = process.stderr.readline()
            if error:
                all_output.append(f"ERROR: {error.strip()}")
                with output_area:
                    st.code("\n".join(all_output))
        
        # Get the return code
        return_code = process.wait()
        all_output.append(f"Process completed with return code: {return_code}")
        
        with output_area:
            st.code("\n".join(all_output))
            
    finally:
        # Clean up the temporary script
        if os.path.exists(script_path):
            os.remove(script_path)

# Function to run a browser-use test script
def create_browser_use_script():
    script_path = "temp_browser_script.py"
    with open(script_path, "w") as f:
        f.write("""
import asyncio
import os
import time
from dotenv import load_dotenv
load_dotenv()

from browser_use import Agent, BrowserSession
from langchain_openai import ChatOpenAI

async def main():
    print("Starting browser-use test...")
    print("Initializing browser session...")
    
    # Create a browser session
    browser_session = BrowserSession(
        browser_type="chromium",
        keep_alive=False,
        headless=True
    )
    
    print("Creating AI agent...")
    # Create an agent
    agent = Agent(
        task="Go to google.com and search for 'browser automation'. Then click on the first result.",
        llm=ChatOpenAI(model="gpt-4o"),
        browser_session=browser_session,
        use_vision=True
    )
    
    print("Running agent...")
    # Run the agent
    result = await agent.run()
    
    print(f"Agent completed with result: {result}")
    print("Test completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
""")
    return script_path

def run_browser_use_test(output_area):
    # Create the browser-use test script
    script_path = create_browser_use_script()
    
    try:
        # Run the script as a subprocess
        process = subprocess.Popen(
            ["python", script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Initialize output collection
        all_output = []
        
        # Stream output in real-time
        while True:
            # Read a line from stdout
            output = process.stdout.readline()
            
            # If the process has finished and there's no more output, break
            if output == '' and process.poll() is not None:
                break
            
            # If there's output, display it
            if output:
                all_output.append(output.strip())
                with output_area:
                    st.code("\n".join(all_output))
            
            # Check for errors
            error = process.stderr.readline()
            if error:
                all_output.append(f"ERROR: {error.strip()}")
                with output_area:
                    st.code("\n".join(all_output))
        
        # Get the return code
        return_code = process.wait()
        all_output.append(f"Process completed with return code: {return_code}")
        
        with output_area:
            st.code("\n".join(all_output))
            
    finally:
        # Clean up the temporary script
        if os.path.exists(script_path):
            os.remove(script_path)

# Main UI
col1, col2 = st.columns(2)

with col1:
    st.markdown("### Simple Output Test")
    if st.button("Run Simple Output Test", key="simple_test", use_container_width=True):
        # Create a container for output
        output_area = st.empty()
        
        with st.spinner("Running test script..."):
            run_subprocess_with_output_streaming(output_area)
        
        st.success("✅ Simple test completed!")

with col2:
    st.markdown("### Browser-Use Test")
    if st.button("Run Browser-Use Test", key="browser_test", use_container_width=True):
        # Create a container for output
        output_area = st.empty()
        
        with st.spinner("Running browser-use test..."):
            run_browser_use_test(output_area)
        
        st.success("✅ Browser-use test completed!")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
    📋 Subprocess Output Streaming Test | 
    Testing real-time terminal output in Streamlit
    </div>
    """, 
    unsafe_allow_html=True
)
