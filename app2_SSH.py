import streamlit as st
import asyncio
import os
import shutil
import time
import subprocess
import json
import re
import sys
import threading
from io import StringIO
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from browser_use import Agent, BrowserSession
from langchain_openai import ChatOpenAI

# Configure Streamlit page
st.set_page_config(
    page_title="APN Lookup Tool", 
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Create a simple pipe to capture output
class OutputCapture:
    def __init__(self):
        self.output = []
        self.lock = threading.Lock()
        
    def write(self, text):
        with self.lock:
            self.output.append(text)
            # Keep only the last 1000 lines to avoid memory issues
            if len(self.output) > 1000:
                self.output = self.output[-1000:]
        # Also write to the original stdout so we can see in terminal
        original_stdout.write(text)
        
    def get_output(self):
        with self.lock:
            return "".join(self.output)
    
    def clear(self):
        with self.lock:
            self.output = []
    
    def flush(self):
        # Required for stdout compatibility
        pass

# Global output capture
output_capture = OutputCapture()

# Store the original stdout
original_stdout = sys.stdout

# Redirect stdout to our capture
sys.stdout = output_capture

class APNSearcher:
    """APN search class that wraps the browser automation logic"""
    
    def __init__(self):
        self.llm = ChatOpenAI(model="gpt-4o")
    
    def cleanup_browser_processes(self):
        """Kill any existing browser processes that might conflict"""
        try:
            subprocess.run(["pkill", "-f", "Chromium"], capture_output=True)
            subprocess.run(["pkill", "-f", "chrome"], capture_output=True)
            time.sleep(2)
            return "🧹 Cleaned up existing browser processes"
        except Exception as e:
            return f"⚠️ Browser cleanup warning: {e}"

    def cleanup_browser_profile(self):
        """Remove existing browser profile to avoid conflicts"""
        try:
            profile_path = os.path.expanduser("~/.config/browseruse/profiles/default")
            if os.path.exists(profile_path):
                shutil.rmtree(profile_path)
                return "🧹 Cleaned up browser profile directory"
        except Exception as e:
            return f"⚠️ Profile cleanup warning: {e}"

    async def search_apn(self, address, county, state="TX", output_area=None):
        """
        Main APN search function
        Args:
            address: Property address (e.g., "306 Main St, Tuleta")
            county: County name (e.g., "Bee")
            state: State abbreviation (e.g., "TX")
            output_area: Streamlit container for displaying output
        """
        # Clear previous output
        output_capture.clear()
        
        # Print some initial info that will be captured
        print(f"Starting APN search for {address} in {county}, {state}")
        print("Initializing browser automation...")
        
        # Always use headless mode for corporate environments
        headless = True
        
        # Clean up any existing browser conflicts
        cleanup_msg1 = self.cleanup_browser_processes()
        cleanup_msg2 = self.cleanup_browser_profile()
        print(f"Browser cleanup: {cleanup_msg1}, {cleanup_msg2}")
        
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)
        
        # Parse address components
        address_parts = address.split()
        street_number = address_parts[0] if address_parts else "306"
        street_name = " ".join(address_parts[1:]).replace("St,", "").replace("St", "").strip() if len(address_parts) > 1 else "Main"
        
        # Create dynamic task based on inputs - FOCUSED ON APN
        task = f"""
        Step 1. Navigate directly to https://publicrecords.netronline.com/state/{state} and select "{county}" from the county list

        Step 2. if "Name" column contains "Appraisal District" >> in that row click "Go to Data Online" button [scroll UP & DOWN, to make sure that you are in the correct row whose "Name" column contains "Appraisal District"]

        Step 3. On the county website, locate and click "Property Search" >> then on next page >> click "by address" button

        Step 4. Enter "{street_number}" in street number field and "{street_name}" in street name field (adjust format if needed; use city name if prompted)

        Step 5. Review search results and select the property matching {address} (if multiple results appear, compare all address components)
        
        step 5.1: if Property address is asked, use "{street_number} {street_name}" 

        Step 6. On the property details page, locate and extract the "APN" or "Geographic ID" or "Parcel Number" - this is the MOST IMPORTANT data to capture (document the exact format, e.g., "57600-00030-05000-000000")
        
        Step 7: click the row with address matching {address} to view details and confirm the APN number is visible
        """
        
        # Start a thread to update the output area
        def update_output():
            while True:
                if output_area:
                    with output_area:
                        st.code(output_capture.get_output())
                time.sleep(0.5)
        
        update_thread = threading.Thread(target=update_output, daemon=True)
        update_thread.start()
        
        # Create a unique browser session with custom profile
        unique_profile = f"profile_{int(time.time())}"
        browser_session = BrowserSession(
            browser_type="chromium",
            user_data_dir=f"~/.config/browseruse/profiles/{unique_profile}",
            keep_alive=False,
            headless=headless
        )
        
        # Create an agent with detailed configuration
        agent = Agent(
            task=task,
            llm=self.llm,
            browser_session=browser_session,
            use_vision=True,
            save_conversation_path=f"logs/apn_search_{int(time.time())}"
        )
        
        try:
            # Add retry logic
            max_retries = 3
            result = None
            
            for attempt in range(max_retries):
                try:
                    print(f"Starting attempt {attempt+1}/{max_retries}")
                    result = await agent.run()
                    print("Agent run completed successfully")
                    break
                except Exception as e:
                    if attempt < max_retries - 1:
                        print(f"Attempt {attempt+1} failed: {str(e)}. Retrying...")
                        time.sleep(2)  # Wait before retry
                    else:
                        print(f"All {max_retries} attempts failed: {str(e)}")
                        raise
            
            # Parse the result to extract structured data
            parsed_result = self.parse_apn_result(str(result), address)
            
            return {
                "success": True,
                "data": parsed_result,
                "cleanup_messages": [cleanup_msg1, cleanup_msg2],
                "raw_result": str(result)
            }
            
        except Exception as e:
            print(f"Search failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "cleanup_messages": [cleanup_msg1, cleanup_msg2]
            }
        
        finally:
            # Clean up the unique profile after execution
            try:
                profile_path = os.path.expanduser(f"~/.config/browseruse/profiles/{unique_profile}")
                if os.path.exists(profile_path):
                    shutil.rmtree(profile_path)
                    print(f"Cleaned up profile: {unique_profile}")
            except Exception as e:
                print(f"Profile cleanup error: {str(e)}")

    def parse_apn_result(self, result_text, original_address):
        """Parse the search result to extract APN and property data"""
        
        # ENHANCED APN EXTRACTION - Multiple patterns to catch different formats
        apn_number = None
        
        # Look for APN patterns in the result text
        apn_patterns = [
            # Quoted patterns (most reliable)
            r"Geographic ID.*?['\"]([0-9-]{15,25})['\"]",
            r"APN.*?['\"]([0-9-]{15,25})['\"]", 
            r"Parcel Number.*?['\"]([0-9-]{15,25})['\"]",
            r"['\"](\d{5}-\d{5}-\d{5}-\d{6})['\"]",
            r"['\"](\d{21})['\"]",
            
            # Unquoted patterns
            r"Geographic ID.*?(\d{5}-\d{5}-\d{5}-\d{6})",
            r"Geographic ID.*?(\d{21})",
            r"APN.*?(\d{5}-\d{5}-\d{5}-\d{6})",
            r"APN.*?(\d{21})",
            r"Parcel Number.*?(\d{5}-\d{5}-\d{5}-\d{6})",
            r"Parcel Number.*?(\d{21})",
            
            # Standalone patterns (be more careful with these)
            r"(\d{5}-\d{5}-\d{5}-\d{6})",
            r"(\d{21})"
        ]
        
        for pattern in apn_patterns:
            matches = re.findall(pattern, result_text, re.IGNORECASE)
            if matches:
                for match in matches:
                    # Validate that this looks like a real APN
                    if len(match) >= 15 and (match.count('-') >= 3 or len(match) == 21):
                        apn_number = match
                        break
                if apn_number:
                    break
        
        # Extract owner information
        owner = None
        owner_patterns = [
            r"Owner Name.*?([A-Z][A-Z\s]+[A-Z])",
            r"Owner.*?([A-Z][A-Z\s]+[A-Z])",
            r"(VASQUEZ[A-Z\s]+)",
        ]
        for pattern in owner_patterns:
            match = re.search(pattern, result_text)
            if match:
                owner = match.group(1).strip()
                break
        
        # Extract appraised value
        value = None
        value_patterns = [
            r"Appraised Value.*?(\$[\d,]+)",
            r"Appraised.*?(\$[\d,]+)",
            r"Value.*?(\$[\d,]+)",
            r"(\$[\d,]+)"
        ]
        for pattern in value_patterns:
            match = re.search(pattern, result_text)
            if match:
                value = match.group(1) if match.groups() else match.group(0)
                break
        
        return {
            "address": original_address,
            "apn_number": apn_number or "APN not found - check raw result",
            "owner": owner or "Not found",
            "appraised_value": value or "Not found",
            "search_timestamp": datetime.now().isoformat(),
            "search_status": "SUCCESS" if apn_number else "APN_NOT_FOUND"
        }

def save_search_history(search_data):
    """Save search history to a JSON file"""
     # check if logs directory exists, if not create it
    os.makedirs("logs", exist_ok=True)
    
    history_file = "logs/apn_search_history.json"
    
    try:
        if os.path.exists(history_file):
            with open(history_file, 'r') as f:
                history = json.load(f)
        else:
            history = []
        
        history.append(search_data)
        
        # Keep only last 50 searches
        history = history[-50:]
        
        with open(history_file, 'w') as f:
            json.dump(history, f, indent=2)
            
    except Exception as e:
        st.error(f"Failed to save search history: {e}")
        print(f"Failed to save search history: {e}")

def load_search_history():
    """Load search history from JSON file"""
    history_file = "logs/apn_search_history.json"
    
    try:
        if os.path.exists(history_file):
            with open(history_file, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        st.error(f"Failed to load search history: {e}")
        print(f"Failed to load search history: {e}")
        return []

def main():
    st.title("🏠 Corporate APN Lookup Tool")
    st.markdown("### AI-Powered Property APN (Assessor's Parcel Number) Search")
    
    # Sidebar configuration
    st.sidebar.header("🔧 Search Parameters")
    st.sidebar.markdown("Configure your APN search below:")
    
    # Input fields in sidebar
    address = st.sidebar.text_input(
        "🏠 Property Address", 
        placeholder="306 Main", # instead of "306 Main St, Tuleta"
        help="Enter house number and initial street name (e.g., '306 Main' or '123 Elm')"
        )
    
    state = st.sidebar.selectbox(
        "🗺️ State", 
        ["TX", "CA", "FL", "NY", "IL"],
        help="Select the state (currently optimized for TX)"
    )
    
    county = st.sidebar.text_input(
        "🏛️ County", 
        placeholder="Bee",
        help="Enter the county name"
    )
    
    # Advanced options
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Advanced Options")
    
    show_debug = st.sidebar.checkbox(
        "🐛 Show Debug Info", 
        value=False,
        help="Display detailed execution information"
    )
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("#### 🔍 APN Search")
        
        if st.button("🚀 Find APN Number", type="primary", use_container_width=True):
            if address and county:
                # Create progress indicators
                progress_bar = st.progress(0)
                progress_text = st.empty()
                
                # Create a container for live output
                st.markdown("### 🖥️ Live Browser Automation Progress")
                output_area = st.empty()
                
                with st.spinner("🤖 AI Agent is searching for APN..."):
                    try:
                        # Update initial progress
                        progress_text.text("Initializing browser automation...")
                        progress_bar.progress(10)
                        
                        # Run the APN search
                        searcher = APNSearcher()
                        
                        result = asyncio.run(
                            searcher.search_apn(
                                address, 
                                county, 
                                state, 
                                output_area=output_area
                            )
                        )
                        
                        progress_bar.progress(100)
                        progress_text.text("Processing APN search results...")
                        
                        if result["success"]:
                            progress_text.text("✅ APN search completed successfully!")
                            
                            property_data = result["data"]
                            
                            if property_data.get('search_status') == 'SUCCESS':
                                st.success("✅ APN Number Found!")
                            else:
                                st.warning("⚠️ APN search completed but APN number not clearly identified")
                            
                            # Display results in a nice format
                            st.markdown("### 📋 Property APN Information")
                            
                            col_a, col_b = st.columns(2)
                            
                            with col_a:
                                st.metric(
                                    label="🆔 APN Number",
                                    value=property_data.get('apn_number', 'Not found'),
                                    help="Assessor's Parcel Number - Primary identifier"
                                )
                                st.metric(
                                    label="🏠 Address",
                                    value=property_data.get('address', 'Not found')
                                )
                            
                            with col_b:
                                st.metric(
                                    label="👤 Owner",
                                    value=property_data.get('owner', 'Not found')
                                )
                                st.metric(
                                    label="💰 Appraised Value",
                                    value=property_data.get('appraised_value', 'Not found')
                                )
                            
                            # JSON view with APN focus
                            with st.expander("📄 Detailed Results (JSON)"):
                                st.json(property_data)
                            
                            # Debug information
                            if show_debug:
                                with st.expander("🐛 Debug Information"):
                                    st.text("Cleanup Messages:")
                                    for msg in result.get("cleanup_messages", []):
                                        st.text(f"• {msg}")
                                    
                                    st.text("Raw Result (first 1000 chars):")
                                    raw_result = result.get("raw_result", "No raw result")
                                    st.text(raw_result[:1000] + "..." if len(raw_result) > 1000 else raw_result)
                            
                            # Save to history
                            save_search_history(property_data)
                            
                        else:
                            progress_bar.progress(100)
                            progress_text.text("❌ APN search failed")
                            st.error(f"❌ APN search failed: {result.get('error', 'Unknown error')}")
                            
                            if show_debug:
                                with st.expander("🐛 Debug Information"):
                                    st.text("Cleanup Messages:")
                                    for msg in result.get("cleanup_messages", []):
                                        st.text(f"• {msg}")
                        
                    except Exception as e:
                        progress_bar.progress(100)
                        progress_text.text("❌ Unexpected error occurred")
                        st.error(f"❌ Unexpected error: {str(e)}")
                        print(f"Unexpected error: {str(e)}")
                        
                        if show_debug:
                            st.exception(e)
            else:
                st.warning("⚠️ Please enter both address and county")
    
    with col2:
        st.markdown("#### 📊 APN Search History")
        
        if st.button("🔄 Refresh History", use_container_width=True):
            st.rerun()
        
        # Load and display search history
        history = load_search_history()
        
        if history:
            st.markdown(f"**Recent APN Searches ({len(history)})**")
            
            for i, search in enumerate(reversed(history[-5:])):  # Show last 5
                with st.expander(f"🏠 {search.get('address', 'Unknown')}"):
                    st.text(f"APN: {search.get('apn_number', 'N/A')}")
                    st.text(f"Owner: {search.get('owner', 'N/A')}")
                    st.text(f"Value: {search.get('appraised_value', 'N/A')}")
                    st.text(f"Status: {search.get('search_status', 'N/A')}")
                    st.text(f"Date: {search.get('search_timestamp', 'N/A')}")
        else:
            st.info("No APN search history yet. Run your first search!")
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
        🤖 Powered by AI Browser Automation | 
        Built with Streamlit & browser-use | 
        🏠 APN Lookup Tool v2.0
        </div>
        """, 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
