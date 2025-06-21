import streamlit as st
import os
import time
import threading
import asyncio
import tempfile
from dotenv import load_dotenv
load_dotenv()

# Configure Streamlit page
st.set_page_config(
    page_title="Fragment Output Test", 
    page_icon="📋",
    layout="wide"
)

st.title("📋 Fragment Output Streaming Test")
st.markdown("### Testing real-time terminal output streaming using Streamlit fragments")

# Create a file to store the output
output_file = "browser_output.log"

# Function to run browser-use in a separate thread and redirect output to a file
def run_browser_use_with_output_to_file():
    # Create a temporary script that will run browser-use and redirect output to a file
    script = f"""
import asyncio
import os
import sys
from dotenv import load_dotenv
load_dotenv()

from browser_use import Agent, BrowserSession
from langchain_openai import ChatOpenAI

async def main():
    # Create a browser session
    browser_session = BrowserSession(
        browser_type="chromium",
        keep_alive=False,
        headless=True
    )
    
    # Create an agent
    agent = Agent(
        task="Go to google.com and search for 'browser automation'. Then click on the first result.",
        llm=ChatOpenAI(model="gpt-4o"),
        browser_session=browser_session,
        use_vision=True
    )
    
    # Run the agent
    result = await agent.run()
    print(f"Agent completed with result: {{result}}")

if __name__ == "__main__":
    asyncio.run(main())
"""
    
    # Write the script to a temporary file
    with tempfile.NamedTemporaryFile(suffix='.py', delete=False) as f:
        f.write(script.encode())
        script_path = f.name
    
    try:
        # Run the script and redirect output to the file
        os.system(f"python {script_path} > {output_file} 2>&1")
    finally:
        # Clean up the temporary script
        os.unlink(script_path)

# Main UI
col1, col2 = st.columns(2)

with col1:
    st.markdown("### Browser-Use Test with File Output")
    if st.button("Run Browser-Use Test", key="browser_test", use_container_width=True):
        # Clear any existing output file
        if os.path.exists(output_file):
            os.remove(output_file)
        
        # Create an empty file
        with open(output_file, "w") as f:
            pass
        
        # Start the browser-use process in a separate thread
        thread = threading.Thread(target=run_browser_use_with_output_to_file)
        thread.daemon = True
        thread.start()
        
        st.success("✅ Browser-use test started! Output will appear below.")

with col2:
    st.markdown("### Output Monitor")
    
    # Use experimental fragment to update the output display
    @st.experimental_fragment(run_every=0.5)
    def display_output():
        if os.path.exists(output_file):
            try:
                with open(output_file, "r") as f:
                    content = f.read()
                if content:
                    st.code(content)
                else:
                    st.info("Waiting for output...")
            except Exception as e:
                st.error(f"Error reading output file: {e}")
        else:
            st.info("Output file not created yet...")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
    📋 Fragment Output Streaming Test | 
    Testing real-time terminal output in Streamlit using fragments
    </div>
    """, 
    unsafe_allow_html=True
)
