import streamlit as st
import asyncio
import os
import shutil
import time
import subprocess
import json
import re
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

    async def search_apn(self, address, county, state="TX", headless=True, verification_prompt=None):
        """
        Main APN search function
        Args:
            address: Property address (e.g., "306 Main St, Tuleta")
            county: County name (e.g., "Bee")
            state: State abbreviation (e.g., "TX")
            headless: Run browser in headless mode (defaults to True)
            verification_prompt: Optional text to verify against property data
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
        
        # Create dynamic task for APN search
        apn_search_task = f"""
        Step 1. Navigate directly to https://publicrecords.netronline.com/state/{state} and select "{county}" from the county list

        Step 2. if "Name" column contains "Appraisal District" >> in that row click "Go to Data Online" button [scroll UP & DOWN, to make sure that you are in the correct row whose "Name" column contains "Appraisal District"]

        Step 3. On the county website, locate and click "Property Search" >> then on next page >> click "by address" button

        Step 4. Enter "{street_number}" in street number field and "{street_name}" in street name field (adjust format if needed; use city name if prompted)

        Step 5. Review search results and select the property matching {address} (if multiple results appear, compare all address components)
        
        step 5.1: if Property address is asked, use "{street_number} {street_name}" 

        Step 6. On the property details page, locate and extract the "APN" or "Geographic ID" or "Parcel Number" - this is the MOST IMPORTANT data to capture (document the exact format, e.g., "57600-00030-05000-000000")
        
        Step 7: click the row with address matching {address} to view details and confirm the APN number is visible
        """
        
        try:
            # Create a shared browser session
            unique_profile = f"profile_{int(time.time())}"
            shared_session = BrowserSession(
                browser_type="chromium",
                user_data_dir=f"~/.config/browseruse/profiles/{unique_profile}",
                keep_alive=True,  # Keep browser open between agents
                headless=headless  # Use the headless parameter from UI
            )
            await shared_session.start()  # Start session manually
            
            # Agent 1: Find APN
            agent1 = Agent(
                task=apn_search_task,
                llm=self.llm,
                browser_session=shared_session,
                use_vision=True,
                save_conversation_path=f"logs/apn_search_{int(time.time())}"
            )
            apn_result = await agent1.run()
            
            # Parse initial results
            initial_parsed_result = self.parse_apn_result(str(apn_result), address)
            
            # Only run verification if we found an APN and have a verification prompt
            if initial_parsed_result.get("apn_number") != "APN not found - check raw result" and verification_prompt:
                # Extract the property details URL from agent1's history
                property_urls = apn_result.urls()
                property_detail_url = property_urls[-1] if property_urls else None
                
                # Agent 2: Verify information with direct URL navigation
                verification_task = f"""
                Navigate directly to this URL: {property_detail_url}
                
                Your ONLY task is to extract the EXACT text from the Legal Description field.
                
                1. Find the field labeled "Legal Description" on the page
                2. Extract the COMPLETE TEXT VALUE from this field
                3. Report ONLY the exact text you found, using this format:
                   "Legal Description: [exact text]"
                
                DO NOT use phrases like "field contains" or "I found" - extract and report the ACTUAL TEXT VALUE.
                
                Example of correct response:
                "Legal Description: TULETA BLK 3 LOTS 5 & 6"
                
                This is the ONLY information you need to extract. Do not extract any other fields.
                """
                
                agent2 = Agent(
                    task=verification_task,
                    llm=self.llm,
                    browser_session=shared_session,  # Re-use the same session
                    use_vision=True,
                    save_conversation_path=f"logs/verification_{int(time.time())}"
                )
                verification_result = await agent2.run()
                
                # Parse verification results
                legal_description = self.parse_legal_description(str(verification_result))
                
                # Check for semantic match using LLM
                is_semantic_match = False
                if legal_description:  # Empty string is falsy in Python
                    is_semantic_match = await self.check_semantic_match_with_llm(
                        legal_description, 
                        verification_prompt
                    )
                
                # Add verification results to the initial results
                initial_parsed_result["verification_info"] = legal_description if legal_description else "Not found"
                initial_parsed_result["verification_prompt"] = verification_prompt
                initial_parsed_result["is_semantic_match"] = is_semantic_match
            elif verification_prompt:
                # If we have a verification prompt but no APN, add placeholder verification info
                initial_parsed_result["verification_info"] = "Not found - APN search failed"
                initial_parsed_result["verification_prompt"] = verification_prompt
            
            # Close the shared session
            await shared_session.close()
            
            return {
                "success": True,
                "data": initial_parsed_result,
                "cleanup_messages": [cleanup_msg1, cleanup_msg2],
                "raw_result": str(apn_result) + (f"\n\nVERIFICATION:\n{str(verification_result)}" if 'verification_result' in locals() else "")
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

    def parse_legal_description(self, result_text):
        """Parse the result to extract the legal description"""
        # Print the raw result for debugging
        print("\n--- RAW AGENT RESULT ---")
        print(result_text[:200] + "..." if len(result_text) > 200 else result_text)
        
        # First try to extract from the 'text' field in the done action
        done_text_pattern = r"'done':\s*\{\s*'text':\s*'Legal Description:\s*([^']+)',"
        match = re.search(done_text_pattern, result_text)
        if match:
            return match.group(1).strip()
            
        # Define generic patterns to extract legal description
        patterns = [
            # Standard format patterns
            r"Legal Description:\s*([^\n,'\"]+)",
            r"Legal Description[:\s]+([^\n,'\"]+)",
            
            # Quoted value patterns
            r"Legal Description[:\s]+[\"']([^\"']+)[\"']",
            r"[\"']Legal Description[\"'][:\s]+[\"']([^\"']+)[\"']",
            
            # JSON-like format patterns
            r"\"Legal ?Description\":\s*\"([^\"]+)\"",
            r"'Legal ?Description':\s*'([^']+)'",
            
            # General field-value patterns
            r"(?:field|value|text)[:\s]+[\"']([^\"']+)[\"'].*?[Ll]egal [Dd]escription",
            r"[Ll]egal [Dd]escription.*?(?:field|value|text)[:\s]+[\"']([^\"']+)[\"']",
            
            # Extracted content patterns
            r"extracted.*?[Ll]egal [Dd]escription[:\s]+([^\n,'\"]+)",
            r"[Ll]egal [Dd]escription.*?extracted[:\s]+([^\n,'\"]+)",
        ]
        
        # Try each pattern
        for pattern in patterns:
            match = re.search(pattern, result_text, re.IGNORECASE)
            if match:
                extracted_text = match.group(1).strip()
                # Filter out common phrases that aren't actual values
                if extracted_text.lower() not in ["field contains", "the field contains", "contains", "is", "shows"]:
                    return extracted_text
        
        # If no match found, return empty string
        return ""
    
    async def check_semantic_match_with_llm(self, legal_description, verification_prompt):
        """Use LLM to check if legal description and verification prompt are semantically similar"""
        prompt = f"""
        I need to determine if two property descriptions refer to the same property.
        
        Description 1: {legal_description}
        Description 2: {verification_prompt}
        
        Do these descriptions refer to the same property? Consider that they might use different formats or abbreviations.
        
        Answer with ONLY 'Yes' or 'No'.
        """
        
        response = await self.llm.ainvoke(prompt)
        result = response.content.strip().lower()
        
        print(f"LLM Response: {result}")
        
        # Check if the response indicates a match
        return "yes" in result.lower()
        
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
    
    verification_prompt = st.sidebar.selectbox(
        "🔍 Verification Info", 
        ["Block 3, Lot 5 & 6", "TULETA BLK 3 LOTS 5 & 6", "VASQUEZ LETRICIA GAYLE", "306 MAIN"],
        index=0,
        help="Select information to verify against property data"
    )
    
    # Advanced options
    st.sidebar.markdown("---")
    st.sidebar.subheader("⚙️ Advanced Options")
    
    # Single source of truth for headless mode - defaults to True to avoid XServer errors
    headless_mode = st.sidebar.checkbox(
        "🖥️ Headless Mode", 
        value=True,
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
        st.markdown("#### 🔍 APN Search")
        
        if st.button("🚀 Find APN Number", type="primary", use_container_width=True):
            if address and county:
                # Create progress indicators
                progress_bar = st.progress(0)
                status_text = st.empty()
                
                with st.spinner("🤖 AI Agent is searching for APN..."):
                    try:
                        # Update progress
                        progress_bar.progress(10)
                        status_text.text("Initializing browser automation...")
                        
                        # Run the APN search
                        searcher = APNSearcher()
                        
                        progress_bar.progress(30)
                        status_text.text("Navigating to property records website...")
                        
                        result = asyncio.run(
                            searcher.search_apn(address, county, state, headless_mode, verification_prompt)
                        )
                        
                        progress_bar.progress(90)
                        status_text.text("Processing APN search results...")
                        
                        if result["success"]:
                            progress_bar.progress(100)
                            status_text.text("✅ APN search completed successfully!")
                            
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
                            
                            # Display verification results if available
                            if 'verification_info' in property_data:
                                st.markdown("### 🔍 Verification Results")
                                st.info(f"**Verified against:** {property_data.get('verification_prompt', 'N/A')}")
                                st.success(f"**Found:** {property_data.get('verification_info', 'Not found')}")
                                
                                # Display semantic match result
                                is_match = property_data.get('is_semantic_match', False)
                                if is_match:
                                    st.success("✅ **Semantic Match:** The descriptions refer to the same property")
                                else:
                                    st.warning("⚠️ **No Semantic Match:** The descriptions may refer to different properties")
                            
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
                            status_text.text("❌ APN search failed")
                            st.error(f"❌ APN search failed: {result.get('error', 'Unknown error')}")
                            
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
                    
                    # Display verification information if available
                    if 'verification_info' in search:
                        st.text(f"Verification: {search.get('verification_info', 'N/A')}")
                        if search.get('verification_prompt'):
                            st.text(f"Verified against: {search.get('verification_prompt', 'N/A')}")
                        if 'is_semantic_match' in search:
                            match_status = "✅ Match" if search.get('is_semantic_match') else "❌ No Match"
                            st.text(f"Semantic Match: {match_status}")
        else:
            st.info("No APN search history yet. Run your first search!")
    
    # Footer
    st.markdown("---")
    st.markdown(
        """
        <div style='text-align: center; color: #666;'>
        🤖 Powered by AI Browser Automation | 
        Built with Streamlit & browser-use | 
        🏠 APN Lookup Tool v4.0
        </div>
        """, 
        unsafe_allow_html=True
    )

if __name__ == "__main__":
    main()
