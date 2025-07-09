import unittest
import asyncio
import os
import json
import re
from dotenv import load_dotenv
load_dotenv()

from browser_use import Agent, BrowserSession
from langchain_openai import ChatOpenAI

class TestLegalDescriptionExtraction(unittest.TestCase):
    """Unit test for extracting Legal Description from property details page"""
    
    def setUp(self):
        """Set up test environment"""
        self.llm = ChatOpenAI(model="gpt-4o")
        self.test_url = "https://esearch.beecad.org/Property/View/9763?year=2025&ownerId=25544"
        self.expected_legal_description = "TULETA BLK 3 LOTS 5 & 6"
        self.verification_prompt = "Block 3, Lot 5 & 6"
    
    def test_legal_description_extraction(self):
        """Test that the agent can extract the Legal Description field"""
        # Run the async test
        result = asyncio.run(self.extract_legal_description())
        
        # Assert that we got a result
        self.assertIsNotNone(result)
        
        # Parse the result to extract the legal description
        legal_description = self.parse_legal_description(str(result))
        
        # Print the extracted legal description
        print("\n--- EXTRACTED LEGAL DESCRIPTION ---")
        print(f"Legal Description: {legal_description}")
        
        # Print the full JSON result
        print("\n--- FULL JSON RESULT ---")
        json_result = {"legal_description": legal_description}
        print(json.dumps(json_result, indent=2))
        
        # Check for semantic match using LLM
        is_semantic_match = asyncio.run(self.check_semantic_match_with_llm(
            legal_description, 
            self.verification_prompt
        ))
        
        # Print semantic match result
        print("\n--- SEMANTIC MATCH RESULT ---")
        print(f"Verification Prompt: {self.verification_prompt}")
        print(f"Legal Description: {legal_description}")
        print(f"Is Semantic Match: {is_semantic_match}")
        
        # Assert that there is a semantic match
        self.assertTrue(is_semantic_match, 
                       f"Verification prompt '{self.verification_prompt}' does not semantically match legal description '{legal_description}'")
    
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
    
    async def extract_legal_description(self):
        """Use an agent to extract the legal description from the property details page"""
        # Create a browser session
        browser_session = BrowserSession(
            browser_type="chromium",
            headless=True  # Run headless for tests
        )
        
        # Define the verification task - focused ONLY on Legal Description
        verification_task = f"""
        Navigate directly to this URL: {self.test_url}
        
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
        
        # Create the agent
        agent = Agent(
            task=verification_task,
            llm=self.llm,
            browser_session=browser_session,
            use_vision=True
        )
        
        try:
            # Run the agent
            result = await agent.run()
            return result
        finally:
            # Always close the browser session
            await browser_session.close()
    
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

if __name__ == "__main__":
    unittest.main()
