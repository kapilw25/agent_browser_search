
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
