import os
from google import genai
import json

class GeminiService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            print("Error: GEMINI_API_KEY not set in environment variables.")
            self.client = None
            return
        
        # Debbuging: Print masked key to verify it's loaded
        masked_key = f"{self.api_key[:5]}...{self.api_key[-5:]}" if len(self.api_key) > 10 else "***"
        print(f"DEBUG: Gemini Client initialized with Key: {masked_key}")
        
        try:
            self.client = genai.Client(api_key=self.api_key)
        except Exception as e:
            print(f"Error configuring Gemini Client: {e}")
            self.client = None
            
        self.prompt_template = self._load_prompt()

    def _load_prompt(self):
        try:
            prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompts', 'prediction_prompt.txt')
            with open(prompt_path, 'r') as f:
                return f.read()
        except Exception as e:
            print(f"Error loading prompt: {e}")
            return ""

    def get_prediction(self, home_team, away_team, league):
        if not self.client:
            return {"error": "Gemini API not configured or key missing."}

            return {"error": "Prompt template not loaded"}

        prompt = self.prompt_template.format(
            home=home_team,
            away=away_team,
            league=league
        )

        try:
            # Using gemini-2.0-flash as primary, falling back if needed (though flash is usually standard now)
            response = self.client.models.generate_content(
                model='gemini-2.0-flash',
                contents=prompt
            )
            
            if not response.text:
                 return {"error": "Empty response from AI"}

            # Clean up response to ensure valid JSON parsing
            clean_text = response.text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.startswith("```"): # Handle case where lang is not specified
                clean_text = clean_text[3:] 
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]
            
            return json.loads(clean_text)
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg:
                return {"error": "AI is currently busy (Rate Limit Exceeded). Please try again in a minute."}
            print(f"Gemini Prediction Error: {e}")
            return {"error": f"AI Generation failed: {error_msg}"}
