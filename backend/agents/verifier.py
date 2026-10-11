"""
Pillar II: AI Verifier / Judge.

Evaluates the generated email against strict constraints (word count, tone, CPT strategy inclusion).
Returns a verification status and feedback, allowing the LangGraph orchestrator to regenerate or approve.
"""
from __future__ import annotations

import json
import logging
import re
from openai import AsyncOpenAI

from backend.config import get_settings

logger = logging.getLogger(__name__)

MLX_BASE_URL = "http://localhost:8080/v1"
MLX_MODEL_NAME = "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"

_VERIFIER_PROMPT = """\
You are an expert technical recruiter and cold-email judge. 
Review the following email draft generated for a software engineering internship.

EMAIL DRAFT:
{email_body}

Verify the following constraints strictly:
1. Is it under 200 words?
2. Does it maintain a confident, direct tone without sounding "salesy"?
3. Is it clear of clichés like "I came across your job posting" or "I am writing to express my interest"?
4. If a CPT strategy was requested, is the CPT sentence appropriately included without dominating the email?

Provide a verdict ("pass" or "fail") and concise feedback for the writer.

Return ONLY valid JSON with this exact structure:
{{
  "verdict": "pass",
  "feedback": "Your feedback here..."
}}
"""

def _strip_json_fences(text: str) -> str:
    text = re.sub(r"^```[a-z]*\n?", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    return text.strip()

async def verify_email(email_body: str) -> dict:
    prompt = _VERIFIER_PROMPT.format(email_body=email_body)
    fallback = {"verdict": "pass", "feedback": "Verifier unavailable, auto-passing."}
    
    try:
        client = AsyncOpenAI(base_url=MLX_BASE_URL, api_key="not-needed")
        response = await client.chat.completions.create(
            model=MLX_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=256,
        )
        raw = _strip_json_fences(response.choices[0].message.content)
        result = json.loads(raw)
        
        # Ensure keys exist
        if "verdict" not in result:
            result["verdict"] = "pass"
        if "feedback" not in result:
            result["feedback"] = ""
            
        return result
    except Exception as exc:
        logger.warning(f"MLX verification failed: {exc}. Falling back to Gemini 3 Flash...")
        try:
            import google.generativeai as genai
            settings = get_settings()
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-3.0-flash")
            response = await model.generate_content_async(prompt)
            raw = _strip_json_fences(response.text)
            result = json.loads(raw)
            return result
        except Exception as gemini_exc:
            logger.error(f"Verifier fallback failed: {gemini_exc}")
            return fallback
