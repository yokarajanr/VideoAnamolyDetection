import sys
import logging
from config import GEMINI_API_KEYS, GEMINI_MODEL
import google.generativeai as genai

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_vlm():
    if not GEMINI_API_KEYS:
        print("No keys found")
        return
        
    print(f"Using model: {GEMINI_MODEL}")
    genai.configure(api_key=GEMINI_API_KEYS[0])
    model = genai.GenerativeModel(GEMINI_MODEL)
    
    import typing_extensions as typing

    class VLMResponse(typing.TypedDict):
        scene_description: str
        behavioral_analysis: str
        is_anomalous: bool
        confidence_score: int
        risk_level: str

    try:
        response = model.generate_content(
            "Hello",
            generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                response_mime_type="application/json",
                response_schema=VLMResponse,
            ),
        )
        print(f"Response: {response.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_vlm()
