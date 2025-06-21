import streamlit as st
import asyncio
import os
import time
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

async def run_agent_with_screenshots(task, screenshot_container, progress_text, progress_bar):
    # Store screenshots and captions
    screenshots = []
    captions = []
    
    # Create a unique browser session with custom profile
    browser_session = BrowserSession(
        browser_type="chromium",
        keep_alive=False,
        headless=False  # Important: Use non-headless mode
    )
    
    # Create an agent with detailed configuration
    agent = Agent(
        task=task,
        llm=ChatOpenAI(model="gpt-4o"),
        browser_session=browser_session,
        use_vision=True
    )
    
    # Define the screenshot callback function
    async def screenshot_callback(step_num, success):
        try:
            # Update progress
            progress_bar.progress((step_num) / 5)  # Assuming 5 steps max
            progress_text.text(f"Step {step_num}: {'✅' if success else '❌'} Processing...")
            
            # Capture screenshot
            screenshot = await browser_session.screenshot()
            
            if screenshot:
                # Save screenshot to file
                timestamp = int(time.time())
                filename = f"screenshots/step_{step_num}_{timestamp}.png"
                
                with open(filename, "wb") as f:
                    f.write(screenshot)
                
                # Add to collection
                screenshots.append(filename)
                captions.append(f"Step {step_num}")
                
                # Show current screenshot
                with screenshot_container:
                    st.image(screenshot, caption=f"Step {step_num}")
                    st.text(f"Captured at: {time.strftime('%H:%M:%S')}")
        except Exception as e:
            st.error(f"Screenshot error: {str(e)}")
    
    # Set the callback
    agent.on_step_complete = screenshot_callback
    
    # Run the agent
    result = await agent.run()
    
    return result, screenshots, captions

# Main function
if st.button("🚀 Run Browser-Use Agent", type="primary"):
    # Create progress indicators and screenshot area
    progress_bar = st.progress(0)
    progress_text = st.empty()
    
    # Create a dedicated container for screenshots
    st.markdown("### 🖼️ Live Browser Navigation")
    screenshot_container = st.empty()
    
    with st.spinner("🤖 AI Agent is working..."):
        # Simple task for testing
        task = "Go to google.com and search for 'browser automation'. Then click on the first result."
        
        result, screenshots, captions = asyncio.run(
            run_agent_with_screenshots(
                task,
                screenshot_container,
                progress_text,
                progress_bar
            )
        )
        
        # Display completion message
        progress_bar.progress(100)
        progress_text.text("✅ Task completed successfully!")
        
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
                        with open(screenshot_path, "rb") as f:
                            image_bytes = f.read()
                        st.image(image_bytes, caption=caption, use_column_width=True)
                except Exception as e:
                    st.warning(f"Could not load screenshot {screenshot_path}: {str(e)}")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
    📸 Browser-Use Screenshot Test | 
    Simple bridge between screenshot_test.py and app3.py
    </div>
    """, 
    unsafe_allow_html=True
)
