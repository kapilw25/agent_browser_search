import streamlit as st
import asyncio
import os
from playwright.async_api import async_playwright
import time
import base64
from io import BytesIO

# Create screenshots directory if it doesn't exist
os.makedirs("screenshots", exist_ok=True)

# Configure Streamlit page
st.set_page_config(
    page_title="Screenshot Test", 
    page_icon="📸",
    layout="wide"
)

st.title("📸 Screenshot Capture Test")
st.markdown("### Testing screenshot capture and display from xvfb-run")

# Function to capture screenshots with Playwright
async def capture_screenshots():
    screenshots = []
    captions = []
    
    # Create a container for live screenshots
    screenshot_container = st.empty()
    progress_text = st.empty()
    progress_bar = st.progress(0)
    
    # List of websites to visit
    websites = [
        ("https://www.google.com", "Google Homepage"),
        ("https://www.wikipedia.org", "Wikipedia Homepage"),
        ("https://www.github.com", "GitHub Homepage"),
        ("https://www.python.org", "Python Homepage"),
        ("https://streamlit.io", "Streamlit Homepage")
    ]
    
    try:
        async with async_playwright() as p:
            # Launch browser (non-headless since we're using xvfb-run)
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            
            # Visit each website and take screenshots
            for i, (url, caption) in enumerate(websites):
                # Update progress
                progress = (i + 1) / len(websites)
                progress_bar.progress(progress)
                progress_text.text(f"Step {i+1}/{len(websites)}: Navigating to {caption}")
                
                # Navigate to the website
                await page.goto(url, wait_until="networkidle")
                
                # Wait a bit for any animations to complete
                await asyncio.sleep(2)
                
                # Capture screenshot
                screenshot_bytes = await page.screenshot()
                screenshots.append(screenshot_bytes)
                captions.append(caption)
                
                # Display current screenshot
                with screenshot_container.container():
                    st.image(screenshot_bytes, caption=caption)
                    st.text(f"Captured at: {time.strftime('%H:%M:%S')}")
                
                # Save screenshot to file
                with open(f"screenshots/step_{i+1}_{caption.replace(' ', '_')}.png", "wb") as f:
                    f.write(screenshot_bytes)
                
                # Wait a bit before next step
                await asyncio.sleep(1)
            
            # Close browser
            await browser.close()
        
        return screenshots, captions
    
    except Exception as e:
        st.error(f"Error capturing screenshots: {str(e)}")
        return [], []

# Main function
if st.button("🚀 Start Screenshot Test", type="primary"):
    with st.spinner("Capturing screenshots..."):
        screenshots, captions = asyncio.run(capture_screenshots())
    
    if screenshots:
        st.success(f"✅ Successfully captured {len(screenshots)} screenshots!")
        
        # Display all screenshots in a grid
        st.markdown("### 📸 Captured Screenshots")
        
        cols = st.columns(3)
        for i, (screenshot, caption) in enumerate(zip(screenshots, captions)):
            with cols[i % 3]:
                st.image(screenshot, caption=caption, use_container_width=True)
        
        # Show saved files
        st.markdown("### 💾 Saved Screenshot Files")
        for file in sorted(os.listdir("screenshots")):
            if file.endswith(".png"):
                st.text(f"• {file}")
    else:
        st.warning("No screenshots were captured.")

# Footer
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center; color: #666;'>
    📸 Screenshot Capture Test | 
    Running with xvfb-run on SSH
    </div>
    """, 
    unsafe_allow_html=True
)
