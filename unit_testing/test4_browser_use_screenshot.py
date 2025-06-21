import streamlit as st
import asyncio
import os
import time
from playwright.async_api import async_playwright
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

async def run_agent_with_screenshots():
    # Create progress indicators and screenshot area
    progress_bar = st.progress(0)
    progress_text = st.empty()
    
    # Create a dedicated container for screenshots
    st.markdown("### 🖼️ Live Browser Navigation")
    screenshot_container = st.empty()
    
    # Store screenshots and captions
    screenshots = []
    captions = []
    
    # First, launch Playwright directly to have more control
    async with async_playwright() as p:
        # Launch browser (non-headless since we're using xvfb-run)
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Create a BrowserSession using the existing page
        browser_session = BrowserSession(
            page=page,
            keep_alive=False  # Changed to False to avoid the initialization issue
        )
        
        # Create an agent with detailed configuration
        agent = Agent(
            task="Go to google.com and search for 'browser automation'. Then click on the first result.",
            llm=ChatOpenAI(model="gpt-4o"),
            browser_session=browser_session,
            use_vision=True
        )
        
        # Function to take screenshots manually
        async def take_screenshot(step_num, description):
            try:
                # Take screenshot with Playwright directly
                screenshot_bytes = await page.screenshot()
                
                # Save screenshot to file
                timestamp = int(time.time())
                filename = f"screenshots/step_{step_num}_{timestamp}.png"
                
                with open(filename, "wb") as f:
                    f.write(screenshot_bytes)
                
                # Add to collection
                screenshots.append(filename)
                captions.append(f"Step {step_num}: {description}")
                
                # Show current screenshot
                with screenshot_container:
                    st.image(screenshot_bytes, caption=f"Step {step_num}: {description}")
                    st.text(f"Captured at: {time.strftime('%H:%M:%S')}")
                
                # Update progress
                progress_bar.progress(step_num / 5)  # Assuming 5 steps max
                progress_text.text(f"Step {step_num}/5: {description}")
                
            except Exception as e:
                st.error(f"Screenshot error: {str(e)}")
        
        try:
            # Take initial screenshot
            await take_screenshot(0, "Starting browser")
            
            # Start a background task to take screenshots periodically
            async def screenshot_loop():
                step = 1
                while True:
                    await asyncio.sleep(3)  # Take a screenshot every 3 seconds
                    current_url = page.url
                    await take_screenshot(step, f"URL: {current_url}")
                    step += 1
                    if step > 10:  # Limit to 10 screenshots
                        break
            
            # Start the screenshot loop in the background
            screenshot_task = asyncio.create_task(screenshot_loop())
            
            # Run the agent
            result = await agent.run()
            
            # Cancel the screenshot task
            screenshot_task.cancel()
            
            # Take final screenshot
            await take_screenshot(99, "Task completed")
            
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
            
            return result, screenshots, captions
            
        finally:
            # Close the browser
            await browser.close()

# Main function
if st.button("🚀 Run Browser-Use Agent", type="primary"):
    with st.spinner("🤖 AI Agent is working..."):
        result, screenshots, captions = asyncio.run(run_agent_with_screenshots())
        
        # Display completion message
        st.success("✅ Task completed successfully!")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
    📸 Browser-Use Screenshot Test | 
    Using direct Playwright screenshot capture
    </div>
    """, 
    unsafe_allow_html=True
)
