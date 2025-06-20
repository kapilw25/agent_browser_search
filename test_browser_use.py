import asyncio
import os
import shutil
import time
import subprocess
from dotenv import load_dotenv
load_dotenv()

from browser_use import Agent, BrowserSession
from langchain_openai import ChatOpenAI

def cleanup_browser_processes():
    """Kill any existing browser processes that might conflict"""
    try:
        # Kill any existing Chromium processes
        subprocess.run(["pkill", "-f", "Chromium"], capture_output=True)
        subprocess.run(["pkill", "-f", "chrome"], capture_output=True)
        time.sleep(2)  # Wait for processes to terminate
        print("🧹 Cleaned up existing browser processes")
    except Exception as e:
        print(f"⚠️ Browser cleanup warning: {e}")

def cleanup_browser_profile():
    """Remove existing browser profile to avoid conflicts"""
    try:
        profile_path = os.path.expanduser("~/.config/browseruse/profiles/default")
        if os.path.exists(profile_path):
            shutil.rmtree(profile_path)
            print("🧹 Cleaned up browser profile directory")
    except Exception as e:
        print(f"⚠️ Profile cleanup warning: {e}")

async def main():
    print("🚀 Starting browser-use test...")
    
    # Clean up any existing browser conflicts
    cleanup_browser_processes()
    cleanup_browser_profile()
    
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    
    task = """
    Step 1. Navigate directly to https://publicrecords.netronline.com/state/TX and select "Bee" from the county list

    Step 2. if "Name" column contains "Appraisel District" >> in that row click  "Go to Data Online" button [scroll UP & DOWN, to make sure that you are in the correct row whose "Name" column contains "Appraisel District"]

    Step 3. On the county website, locate and click "Property Search" >> then on next page >> click "by address" button

    Step 4. Enter "306" in street number field and "Main" in street name field (adjust format if needed; use "Tuleta" for city if prompted)

    Step 5. Review search results and select the property matching 306 Main St, Tuleta, TX 78162 (if multiple results appear, compare all address components)
    
    step 5.1: if Property addess is asked, use "306 Main" 

    Step 6. On the property details page, locate and extract the "Geographic ID" or "APN" or "Parcel Number" (document the exact format, e.g., "57600-00000")
    
    Step 7: click the row with address matching 306 Main St, Tuleta, TX 78162 to view details
    
    """
    
    print("📋 Task Details:")
    print("=" * 60)
    print(task)
    print("=" * 60)
    
    # Initialize LLM
    llm = ChatOpenAI(model="gpt-4o")
    
    # Create a unique browser session with custom profile
    unique_profile = f"profile_{int(time.time())}"
    browser_session = BrowserSession(
        browser_type="chromium",
        user_data_dir=f"~/.config/browseruse/profiles/{unique_profile}",
        keep_alive=False
    )
    
    # Create an agent with detailed configuration
    agent = Agent(
        task=task,
        llm=llm,
        browser_session=browser_session,
        use_vision=True,                           # Enable vision capabilities
        save_conversation_path="logs/conversation" # Save chat logs
    )
    
    print("🤖 Agent created with vision enabled and logging configured...")
    print(f"📁 Logs will be saved to: logs/conversation")
    print(f"🌐 Using unique browser profile: {unique_profile}")
    print("👁️ Vision capabilities: ENABLED")
    print("\n🚀 Starting task execution...")
    
    try:
        result = await agent.run()
        print("✅ Task completed!")
        print(f"📄 Result: {result}")
        
        # Check if logs were created
        if os.path.exists("logs"):
            log_files = os.listdir("logs")
            if log_files:
                print(f"📝 Log files created: {log_files}")
            else:
                print("📝 No log files found")
        
    except Exception as e:
        print(f"❌ Task failed with error: {e}")
        print("🔄 RESTARTING FROM STEP 1...")
        
        # Clean up failed session
        try:
            if browser_session:
                await browser_session.close()
        except:
            pass
        
        # Clean up browser processes and profiles
        cleanup_browser_processes()
        cleanup_browser_profile()
        
        # Wait a moment before restart
        time.sleep(3)
        
        # RESTART: Create new session and try again
        try:
            print("🚀 RESTART ATTEMPT - Creating new browser session...")
            
            # Create new unique profile for restart
            restart_profile = f"restart_profile_{int(time.time())}"
            restart_browser_session = BrowserSession(
                browser_type="chromium",
                user_data_dir=f"~/.config/browseruse/profiles/{restart_profile}",
                keep_alive=False
            )
            
            # Create new agent for restart
            restart_agent = Agent(
                task=task,
                llm=llm,
                browser_session=restart_browser_session,
                use_vision=True,
                save_conversation_path="logs/restart_conversation"
            )
            
            print("🔄 Executing RESTART attempt...")
            restart_result = await restart_agent.run()
            print("✅ RESTART successful!")
            print(f"📄 Restart Result: {restart_result}")
            
            # Clean up restart profile
            try:
                restart_profile_path = os.path.expanduser(f"~/.config/browseruse/profiles/{restart_profile}")
                if os.path.exists(restart_profile_path):
                    shutil.rmtree(restart_profile_path)
                    print(f"🧹 Cleaned up restart profile: {restart_profile}")
            except Exception as cleanup_error:
                print(f"⚠️ Restart profile cleanup warning: {cleanup_error}")
                
        except Exception as restart_error:
            print(f"❌ RESTART also failed: {restart_error}")
            print("💡 Manual intervention may be required")
    
    finally:
        # Clean up the unique profile after execution
        try:
            profile_path = os.path.expanduser(f"~/.config/browseruse/profiles/{unique_profile}")
            if os.path.exists(profile_path):
                shutil.rmtree(profile_path)
                print(f"🧹 Cleaned up profile: {unique_profile}")
        except Exception as e:
            print(f"⚠️ Profile cleanup warning: {e}")

if __name__ == "__main__":
    asyncio.run(main())
