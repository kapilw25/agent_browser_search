import streamlit as st
import asyncio
import os
import shutil
import time
import subprocess
import json
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

from browser_use import Agent, BrowserSession
from langchain_openai import ChatOpenAI

# Configure Streamlit page
st.set_page_config(
    page_title="Property Search Tool", 
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded"
)

class PropertySearcher:
    """Property search class that wraps the browser automation logic"""
    
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

    async def search_property(self, address, county, state="TX", headless=False):
        """
        Main property search function
        Args:
            address: Property address (e.g., "306 Main St, Tuleta")
            county: County name (e.g., "Bee")
            state: State abbreviation (e.g., "TX")
            headless: Run browser in headless mode
        """
        
        # Clean up any existing browser conflicts
        cleanup_msg1 = self.cleanup_browser_processes()
        cleanup_msg2 = self.cleanup_browser_profile()
        
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)
        
        # Parse address components
        address_parts = address.split()
        street_number = address_parts[0] if address_parts else "306"
        street_name = " ".join(address_parts[1:]).replace("St,", "").replace("St", "").strip() if len(address_parts) > 1 else "Main"
        
        # Create dynamic task based on inputs
        task = f"""
        Step 1. Navigate directly to https://publicrecords.netronline.com/state/{state} and select "{county}" from the county list

        Step 2. if "Name" column contains "Appraisal District" >> in that row click "Go to Data Online" button [scroll UP & DOWN, to make sure that you are in the correct row whose "Name" column contains "Appraisal District"]

        Step 3. On the county website, locate and click "Property Search" >> then on next page >> click "by address" button

        Step 4. Enter "{street_number}" in street number field and "{street_name}" in street name field (adjust format if needed; use city name if prompted)

        Step 5. Review search results and select the property matching {address} (if multiple results appear, compare all address components)
        
        step 5.1: if Property address is asked, use "{street_number} {street_name}" 

        Step 6. On the property details page, locate and extract the "APN" or "Geographic ID" or "Parcel Number" (document the exact format, e.g., "57600-00030-05000-000000")
        
        Step 7: click the row with address matching {address} to view details
        """
        
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
            save_conversation_path=f"logs/search_{int(time.time())}"
        )
        
        try:
            result = await agent.run()
            
            # Parse the result to extract structured data
            parsed_result = self.parse_search_result(str(result), address)
            
            return {
                "success": True,
                "data": parsed_result,
                "cleanup_messages": [cleanup_msg1, cleanup_msg2],
                "raw_result": str(result)
            }
            
        except Exception as e:
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
            except Exception as e:
                pass

    def parse_search_result(self, result_text, original_address):
        """Parse the search result to extract structured property data with focus on APN"""
        
        # Extract APN/Geographic ID patterns - IMPROVED REGEX
        apn_number = None
        if any(keyword in result_text for keyword in ["Geographic ID", "APN", "Parcel Number"]):
            import re
            
            # Enhanced patterns to capture full APN numbers
            patterns = [
                r"Geographic ID.*?['\"]([0-9-]{15,25})['\"]",  # With quotes
                r"Geographic ID.*?(\d{5}-\d{5}-\d{5}-\d{6})",   # Standard format with dashes
                r"Geographic ID.*?(\d{21})",                    # 21-digit format
                r"APN.*?['\"]([0-9-]{15,25})['\"]",            # APN with quotes
                r"APN.*?(\d{5}-\d{5}-\d{5}-\d{6})",           # APN standard format
                r"APN.*?(\d{21})",                             # APN 21-digit
                r"Parcel Number.*?['\"]([0-9-]{15,25})['\"]",  # Parcel with quotes
                r"Parcel Number.*?(\d{5}-\d{5}-\d{5}-\d{6})",  # Parcel standard
                r"Parcel Number.*?(\d{21})",                   # Parcel 21-digit
                r"'(\d{5}-\d{5}-\d{5}-\d{6})'",              # Any quoted standard format
                r"'(\d{21})'",                                 # Any quoted 21-digit
                r"(\d{5}-\d{5}-\d{5}-\d{6})",                # Unquoted standard format
                r"(\d{21})"                                    # Unquoted 21-digit (last resort)
            ]
            
            for pattern in patterns:
                matches = re.findall(pattern, result_text)
                if matches:
                    # Filter out obvious non-APN numbers (like years, small numbers)
                    for match in matches:
                        if len(match) >= 15:  # APN should be at least 15 characters
                            apn_number = match
                            break
                    if apn_number:
                        break
        
        # Extract owner information
        owner = None
        if "Owner" in result_text or "VASQUEZ" in result_text:
            owner_patterns = [
                r"Owner.*?([A-Z][A-Z\s]+[A-Z])",
                r"(VASQUEZ[A-Z\s]+)",
                r"Owner Name.*?([A-Z][A-Z\s]+)"
            ]
            for pattern in owner_patterns:
                match = re.search(pattern, result_text)
                if match:
                    owner = match.group(1).strip()
                    break
        
        # Extract appraised value
        value = None
        value_patterns = [
            r"\$[\d,]+",
            r"Appraised.*?(\$[\d,]+)",
            r"Value.*?(\$[\d,]+)"
        ]
        for pattern in value_patterns:
            match = re.search(pattern, result_text)
            if match:
                value = match.group(0) if not match.groups() else match.group(1)
                break
        
        return {
            "address": original_address,
            "apn_number": apn_number or "APN not found - check raw result",
            "geographic_id": apn_number or "Not found",  # Keep for backward compatibility
            "owner": owner or "Not found",
            "appraised_value": value or "Not found",
            "search_timestamp": datetime.now().isoformat(),
            "raw_search_text": result_text[:500] + "..." if len(result_text) > 500 else result_text  # For debugging
        }

def save_search_history(search_data):
    """Save search history to a JSON file"""
    history_file = "search_history.json"
    
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

def load_search_history():
    """Load search history from JSON file"""
    history_file = "search_history.json"
    
    try:
        if os.path.exists(history_file):
            with open(history_file, 'r') as f:
                return json.load(f)
        return []
    except Exception as e:
        st.error(f"Failed to load search history: {e}")
        return []

def main():
    st.title("🏠 Corporate APN Lookup Tool")
    st.markdown("### AI-Powered Property APN (Assessor's Parcel Number) Search")
    
    # Sidebar configuration
    st.sidebar.header("🔧 Search Parameters")
    st.sidebar.markdown("Configure your property search below:")
    
    # Input fields in sidebar
    address = st.sidebar.text_input(
        "🏠 Property Address", 
        placeholder="306 Main St, Tuleta, TX",
        help="Enter the full property address"
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
    
    headless_mode = st.sidebar.checkbox(
        "🖥️ Headless Mode", 
        value=False,
        help="Run browser in background (faster but no visual feedback)"
    )
    
    show_debug = st.sidebar.checkbox(
        "🐛 Show Debug Info", 
        value=False,
        help="Display detailed execution information"
    )
    
    # Main content area
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.markdown("#### 🔍 Property Search")
        
        if st.button("🚀 Search Property", type="primary", use_container_width=True):
            if address and county:
                # Create progress indicators
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                with st.spinner("🤖 AI Agent is searching property records..."):
                    try:
                        # Update progress
                        progress_bar.progress(10)
                        status_text.text("Initializing browser automation...")
                        
                        # Run the property search
                        searcher = PropertySearcher()
                        
                        progress_bar.progress(30)
                        status_text.text("Navigating to property records website...")
                        
                        result = asyncio.run(
                            searcher.search_property(address, county, state, headless_mode)
                        )
                        
                        progress_bar.progress(90)
                        status_text.text("Processing search results...")
                        
                        if result["success"]:
                            progress_bar.progress(100)
                            status_text.text("✅ Search completed successfully!")
                            
                            st.success("✅ Property Found!")
                            
                            # Display results in a nice format
                            property_data = result["data"]
                            
                            # Main result card
                            st.markdown("### 📋 Property Information")
                            
                            col_a, col_b = st.columns(2)
                            
                            with col_a:
                                st.metric(
                                    label="🆔 Geographic ID/APN",
                                    value=property_data.get('geographic_id', 'Not found')
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
                            
                            # JSON view
                            with st.expander("📄 Detailed Results (JSON)"):
                                st.json(property_data)
                            
                            # Debug information
                            if show_debug:
                                with st.expander("🐛 Debug Information"):
                                    st.text("Cleanup Messages:")
                                    for msg in result.get("cleanup_messages", []):
                                        st.text(f"• {msg}")
                                    
                                    st.text("Raw Result:")
                                    st.text(result.get("raw_result", "No raw result"))
                            
                            # Save to history
                            save_search_history(property_data)
                            
                        else:
                            progress_bar.progress(100)
                            status_text.text("❌ Search failed")
                            st.error(f"❌ Search failed: {result.get('error', 'Unknown error')}")
                            
                            if show_debug:
                                with st.expander("🐛 Debug Information"):
                                    st.text("Cleanup Messages:")
                                    for msg in result.get("cleanup_messages", []):
                                        st.text(f"• {msg}")
                        
                        # Clear progress indicators
                        progress_bar.empty()
                        status_text.empty()
                        
                    except Exception as e:
                        progress_bar.empty()
                        status_text.empty()
                        st.error(f"❌ Unexpected error: {str(e)}")
                        
                        if show_debug:
                            st.exception(e)
            else:
                st.warning("⚠️ Please enter both address and county")
    
    with col2:
        st.markdown("#### 📊 Search History")
        
        if st.button("🔄 Refresh History", use_container_width=True):
            st.rerun()
        
        # Load and display search history
        history = load_search_history()
        
        if history:
            st.markdown(f"**Recent Searches ({len(history)})**")
            
            for i, search in enumerate(reversed(history[-5:])):  # Show last 5
                with st.expander(f"🏠 {search.get('address', 'Unknown')}"):
                    st.text(f"Geographic ID: {search.get('geographic_id', 'N/A')}")
                    st.text(f"Owner: {search.get('owner', 'N/A')}")
                    st.text(f"Value: {search.get('appraised_value', 'N/A')}")
                    st.text(f"Date: {search.get('search_timestamp', 'N/A')}")
        else:
            st.info("No search history yet. Run your first search!")
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
        🤖 Powered by AI Browser Automation | 
        Built with Streamlit & browser-use | 
        🏠 Property Search Tool v1.0
        </div>
        """, 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
