"""
core/vlm_analyzer.py — Vision Language Model scene analysis engine.

Sends camera frames to Gemini 1.5 Flash (or configured VLM) with structured
prompts to obtain JSON scene analysis including:
  - Scene description
  - Detected activities
  - Anomaly identification
  - Risk classification with reasoning
  - Recommended actions
  - Environment type inference

Supports multiple providers: gemini | openai | ollama
"""

import asyncio
import base64
import json
import logging
import os
import time
from typing import Optional

import google.generativeai as genai
from PIL import Image
import io
import httpx

from config import (
    VLM_PROVIDER, GEMINI_API_KEYS, GEMINI_MODEL, GEMINI_FALLBACK_MODEL,
    VLM_COOLDOWN_SECONDS, OLLAMA_VLM_MODEL, OLLAMA_BASE_URL
)
from utils.image_utils import frame_to_bytes
import google.api_core.exceptions

# ── Qwen local server (read directly from env, no config.py change needed) ───
QWEN_BASE_URL: str = os.getenv("QWEN_BASE_URL", "http://127.0.0.1:8081")

logger = logging.getLogger(__name__)

# ── Structured output schema ───────────────────────────────────────────────────
VLM_RESPONSE_SCHEMA = {
    "scene_description": "string — 1-2 sentence description of what is visible",
    "behavioral_analysis": "string — Detailed analysis of body language, intent, and temporal context clues",
    "environment_type": "string — inferred type: home/office/classroom/laboratory/factory/warehouse/parking/corridor/custom",
    "detected_activities": "list of strings — activities observed",
    "objects_of_interest": "list of strings — notable objects",
    "anomalies_found": "list of strings — anomalies detected (empty if none)",
    "is_anomalous": "boolean",
    "confidence_score": "integer — 0 to 100",
    "risk_level": "string — one of: Low, Medium, High, Critical",
    "risk_reasoning": "string — why this risk level was assigned",
    "recommended_action": "string — suggested action for operator",
    "zone_violations_noted": "list of strings — any zone or boundary violations observed",
}


def _build_analysis_prompt(environment_context: str, detections_summary: str) -> str:
    """Build the structured analysis prompt sent to the VLM."""
    return f"""You are a senior CCTV Security Operator with 20+ years of experience in behavioral analysis and threat detection.
Analyze the provided surveillance frame and return ONLY a valid JSON object.

{environment_context}

YOLO Object Detections (automated pre-analysis):
{detections_summary}

Analyze the scene with extreme scrutiny considering:
1. What activities and behaviors are occurring?
2. Are there subtle behavioral clues (posture, panic, sneaking, sudden movements, aggression)?
3. Do these behaviors mismatch the expected activities for this environment?
4. Are there safety violations, unauthorized access, suspicious behavior, or imminent threats?
5. What is the overall risk level and your confidence in this assessment?

Respond ONLY with this exact JSON structure (no markdown, no code blocks, raw JSON only).
CRITICAL FOR SPEED: Keep all text fields EXTREMELY concise (1 short sentence maximum).

{{
  "scene_description": "...",
  "behavioral_analysis": "Brief 1-sentence analysis of intent...",
  "environment_type": "...",
  "detected_activities": ["..."],
  "objects_of_interest": ["..."],
  "anomalies_found": ["..."],
  "is_anomalous": false,
  "confidence_score": 95,
  "risk_level": "Low",
  "risk_reasoning": "...",
  "recommended_action": "...",
  "zone_violations_noted": []
}}

Risk levels: Low (normal), Medium (attention needed), High (alert required), Critical (immediate action needed)."""


class VLMAnalyzer:
    """
    Vision Language Model analyzer for scene understanding.
    
    Implements rate-limiting via cooldown to prevent excessive API calls
    and optional async operation to not block the detection pipeline.
    """

    def __init__(self):
        self._last_call_time: float = 0.0
        self._provider = VLM_PROVIDER
        self._pending = False
        
        self._gemini_keys = GEMINI_API_KEYS
        self._current_key_idx = 0
        self._using_fallback = False
        self._model = None

        if self._provider == "gemini":
            if not self._gemini_keys:
                logger.warning("GEMINI_API_KEY not set. VLM analysis will be skipped.")
            else:
                self._configure_gemini()
        elif self._provider == "ollama":
            logger.info(f"Ollama VLM initialized: {OLLAMA_VLM_MODEL} at {OLLAMA_BASE_URL}")
        elif self._provider == "qwen":
            logger.info(f"Qwen VLM initialized at {QWEN_BASE_URL}/v1/chat/completions")

    def _configure_gemini(self):
        """Configure Gemini SDK with the currently active API key and model."""
        if not self._gemini_keys:
            return
            
        key = self._gemini_keys[self._current_key_idx]
        genai.configure(api_key=key)
        
        model_name = GEMINI_FALLBACK_MODEL if self._using_fallback else GEMINI_MODEL
        self._model = genai.GenerativeModel(model_name)
        
        logger.info(f"Gemini VLM initialized: {model_name} (Key #{self._current_key_idx + 1}/{len(self._gemini_keys)})")

    def _is_cooled_down(self) -> bool:
        return (time.time() - self._last_call_time) >= VLM_COOLDOWN_SECONDS

    def should_analyze(self, has_high_priority: bool, has_violations: bool) -> bool:
        """Determine if VLM analysis should be triggered this frame."""
        if not self._is_cooled_down():
            return False
        if self._pending:
            return False
        return has_high_priority or has_violations

    def _parse_vlm_response(self, text: str) -> dict:
        text = text.strip()
        # Remove Markdown formatting if the model accidentally included it
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
            
        if text.endswith("```"):
            text = text[:-3]
            
        text = text.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            # Attempt to extract JSON object from within surrounding text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start != -1 and end > start:
                try:
                    return json.loads(text[start:end])
                except json.JSONDecodeError:
                    pass
            
            logger.warning(f"Failed to parse VLM response as JSON. Falling back to raw text. Raw: {text[:200]}")
            # Robust Fallback for Moondream: If it didn't return JSON, it probably just returned a sentence.
            # We will use its raw output as the scene description to prevent a crash.
            fallback = self._default_response("Parsed as raw text.")
            
            # Clean up the text a bit
            clean_text = text.replace("{", "").replace("}", "").replace('"', '').strip()
            if clean_text:
                fallback["scene_description"] = clean_text
            
            return fallback

    def _default_response(self, reason: str = "") -> dict:
        return {
            "scene_description": f"VLM analysis unavailable. {reason}",
            "behavioral_analysis": "N/A",
            "environment_type": "unknown",
            "detected_activities": [],
            "objects_of_interest": [],
            "anomalies_found": [],
            "is_anomalous": False,
            "confidence_score": 0,
            "risk_level": "Low",
            "risk_reasoning": "VLM not available.",
            "recommended_action": "Continue monitoring.",
            "zone_violations_noted": [],
        }

    async def analyze_frame_async(
        self,
        frame_bytes: bytes,
        environment_context: str,
        detections_summary: str,
    ) -> dict:
        """
        Async analysis — runs VLM call in thread pool to avoid blocking.
        Returns structured dict with scene analysis.
        """
        if self._provider == "gemini" and not self._gemini_keys:
            return self._default_response("No API key configured.")

        self._pending = True
        self._last_call_time = time.time()

        try:
            if self._provider == "ollama":
                call_fn = lambda: self._call_ollama(frame_bytes, environment_context, detections_summary)
            elif self._provider == "qwen":
                call_fn = lambda: self._call_qwen(frame_bytes, environment_context, detections_summary)
            else:
                call_fn = lambda: self._call_gemini(frame_bytes, environment_context, detections_summary)

            result = await asyncio.get_event_loop().run_in_executor(None, call_fn)
            return result
        except Exception as e:
            logger.error(f"VLM analysis error: {e}")
            return self._default_response(str(e))
        finally:
            self._pending = False

    def _call_gemini(
        self,
        frame_bytes: bytes,
        environment_context: str,
        detections_summary: str,
    ) -> dict:
        """Synchronous Gemini API call with automatic key rotation and model fallback."""
        prompt = _build_analysis_prompt(environment_context, detections_summary)
        image = Image.open(io.BytesIO(frame_bytes))
        
        # Max retries = Try every key with both primary and fallback models
        max_retries = len(self._gemini_keys) * 2 if self._gemini_keys else 1
        
        for attempt in range(max_retries):
            try:
                if not self._model:
                    return self._default_response("No API key configured.")

                safety_settings = [
                    {
                        "category": "HARM_CATEGORY_HARASSMENT",
                        "threshold": "BLOCK_NONE",
                    },
                    {
                        "category": "HARM_CATEGORY_HATE_SPEECH",
                        "threshold": "BLOCK_NONE",
                    },
                    {
                        "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                        "threshold": "BLOCK_NONE",
                    },
                    {
                        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                        "threshold": "BLOCK_NONE",
                    },
                ]
                response = self._model.generate_content(
                    [prompt, image],
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.1,
                        max_output_tokens=2048,
                        response_mime_type="application/json",
                    ),
                    safety_settings=safety_settings
                )
        
                raw = response.text
                logger.debug(f"VLM raw response: {raw[:300]}")
                with open("f:\\anomaly\\vlm_debug.log", "w", encoding="utf-8") as f:
                    f.write(raw)
                return self._parse_vlm_response(raw)
                
            except google.api_core.exceptions.ResourceExhausted as e:
                logger.warning(f"Rate limit hit on Key #{self._current_key_idx + 1}.")
                
                # Step 1: Fallback to secondary model on same key
                if not self._using_fallback:
                    logger.info(f"Failover to model: {GEMINI_FALLBACK_MODEL}")
                    self._using_fallback = True
                    self._configure_gemini()
                else:
                    # Step 2: Both models exhausted, rotate to next API key
                    next_idx = (self._current_key_idx + 1) % len(self._gemini_keys)
                    if next_idx == self._current_key_idx:
                        # Only 1 key available and it's totally exhausted
                        logger.error("All models exhausted on the single available API key.")
                        raise e
                        
                    logger.info(f"Rotating to API Key #{next_idx + 1}...")
                    self._current_key_idx = next_idx
                    self._using_fallback = False # Reset to primary model for new key
                    self._configure_gemini()
                    
                time.sleep(1.0) # Brief pause before retry
            except Exception as e:
                raise e
                
        return self._default_response("All API keys and fallback models rate limited.")

    def _call_ollama(
        self,
        frame_bytes: bytes,
        environment_context: str,
        detections_summary: str,
    ) -> dict:
        """Call local Ollama VLM (e.g., Moondream) for scene analysis."""
        prompt = _build_analysis_prompt(environment_context, detections_summary)
        b64_image = base64.b64encode(frame_bytes).decode("utf-8")

        try:
            response = httpx.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": OLLAMA_VLM_MODEL,
                    "prompt": prompt,
                    "images": [b64_image],
                    "stream": False,
                    "format": "json",
                    "options": {
                        "temperature": 0.1,
                        "num_predict": 800,
                    },
                },
                timeout=60.0,
            )
            response.raise_for_status()
            raw = response.json().get("response", "")
            logger.debug(f"Ollama VLM raw response: {raw[:300]}")
            return self._parse_vlm_response(raw)
        except httpx.TimeoutException:
            logger.error("Ollama VLM timed out (60s).")
            return self._default_response("Ollama timeout.")
        except Exception as e:
            logger.error(f"Ollama VLM error: {e}")
            return self._default_response(str(e))

    def _call_qwen(
        self,
        frame_bytes: bytes,
        environment_context: str,
        detections_summary: str,
    ) -> dict:
        """Call local Qwen3-VL via OpenAI-compatible /v1/chat/completions."""
        prompt = _build_analysis_prompt(environment_context, detections_summary)
        b64_image = base64.b64encode(frame_bytes).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{b64_image}"

        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {"url": data_url},
                        },
                    ],
                }
            ],
            "max_tokens": 800,
            "temperature": 0.1,
        }

        try:
            response = httpx.post(
                f"{QWEN_BASE_URL}/v1/chat/completions",
                json=payload,
                timeout=60.0,
            )
            response.raise_for_status()
            raw = response.json()["choices"][0]["message"]["content"]
            logger.debug(f"Qwen VLM raw response: {raw[:300]}")
            return self._parse_vlm_response(raw)
        except httpx.TimeoutException:
            logger.error("Qwen VLM timed out (60s).")
            return self._default_response("Qwen timeout.")
        except httpx.HTTPStatusError as e:
            logger.error(
                f"Qwen VLM HTTP error {e.response.status_code}: {e.response.text[:200]}"
            )
            return self._default_response(f"Qwen HTTP error {e.response.status_code}.")
        except (KeyError, IndexError) as e:
            logger.error(f"Qwen VLM unexpected response structure: {e}")
            return self._default_response("Qwen response parse error.")
        except Exception as e:
            logger.error(f"Qwen VLM error: {e}")
            return self._default_response(str(e))

    def format_detections_summary(self, detections: list[dict]) -> str:
        """Format YOLO detections as a human-readable string for the VLM prompt."""
        if not detections:
            return "No objects detected by YOLO."

        lines = []
        class_counts: dict[str, int] = {}
        for det in detections:
            cls = det["class"]
            class_counts[cls] = class_counts.get(cls, 0) + 1

        for cls, count in class_counts.items():
            lines.append(f"  - {count}x {cls}")

        # Flag high-priority classes
        high_priority = [d["class"] for d in detections if d.get("is_high_priority")]
        if high_priority:
            lines.append(f"  ⚠ HIGH PRIORITY CLASSES: {', '.join(set(high_priority))}")

        return "\n".join(lines)
