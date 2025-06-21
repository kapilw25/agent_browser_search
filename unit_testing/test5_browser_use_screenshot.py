import streamlit as st
import asyncio
import os
import time
import subprocess
from dotenv import load_dotenv
load_dotenv()

from browser_use import Agent, BrowserSession
from langchain_openai import ChatOpenAI

# Configure Streamlit page
st.set_page_config(
    page_title="Browser-Use Screenshot Test", 
    page_icon="📸",
    layout="wide"
)

# Create screenshots directory if it doesn't exist
os.makedirs("screenshots", exist_ok=True)

st.title("📸 Browser-Use Screenshot Test")
st.markdown("### Testing screenshot capture with browser_use Agent")

# Simple function to run the agent
async def run_agent():
    # Create a browser session
    browser_session = BrowserSession(
        browser_type="chromium",
        keep_alive=False,
        headless=False
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
    return result

# Function to take screenshots using xwd (X Window Dump)
def take_screenshot(filename):
    try:
        # Use xwd to capture the screen and convert to PNG with ImageMagick
        subprocess.run(f"xwd -root | convert xwd:- {filename}", shell=True, check=True)
        return True
    except Exception as e:
        st.error(f"Screenshot error: {str(e)}")
        return False

# Main function
if st.button("🚀 Run Browser-Use Agent", type="primary"):
    # Create progress indicators
    progress_bar = st.progress(0)
    progress_text = st.empty()
    
    # Create a dedicated container for screenshots
    st.markdown("### 🖼️ Live Browser Navigation")
    screenshot_container = st.empty()
    
    # Store screenshots and captions
    screenshots = []
    captions = []
    
    with st.spinner("🤖 AI Agent is working..."):
        # Start a background process to take screenshots
        def take_screenshots_periodically():
            step = 0
            while True:
                # Take a screenshot
                timestamp = int(time.time())
                filename = f"screenshots/step_{step}_{timestamp}.png"
                
                if take_screenshot(filename):
                    screenshots.append(filename)
                    captions.append(f"Step {step}")
                    
                    # Update the UI
                    progress_bar.progress((step % 5) / 5)
                    progress_text.text(f"Step {step}: Taking screenshot")
                    
                    # Display the screenshot
                    try:
                        with screenshot_container:
                            st.image(filename, caption=f"Step {step}")
                            st.text(f"Captured at: {time.strftime('%H:%M:%S')}")
                    except Exception as e:
                        st.error(f"Error displaying screenshot: {str(e)}")
                
                step += 1
                time.sleep(3)  # Take a screenshot every 3 seconds
                
                # Limit to 20 screenshots
                if step >= 20:
                    break
        
        # Start the screenshot process in a separate thread
        import threading
        screenshot_thread = threading.Thread(target=take_screenshots_periodically)
        screenshot_thread.daemon = True
        screenshot_thread.start()
        
        # Run the agent
        result = asyncio.run(run_agent())
        
        # Wait for the screenshot thread to finish
        screenshot_thread.join(timeout=5)
        
        # Display the result
        st.markdown("### 📋 Result")
        st.text(str(result))
        
        # Display all screenshots
        if screenshots:
            st.markdown("### 🔍 All Screenshots")
            
            cols = st.columns(3)
            for i, (screenshot_path, caption) in enumerate(zip(screenshots, captions)):
                try:
                    with cols[i % 3]:
                        st.image(screenshot_path, caption=caption, use_column_width=True)
                except Exception as e:
                    st.warning(f"Could not load screenshot {screenshot_path}: {str(e)}")
        
        # Display completion message
        st.success("✅ Task completed successfully!")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
    📸 Browser-Use Screenshot Test | 
    Using xwd for screenshot capture
    </div>
    """, 
    unsafe_allow_html=True
)
