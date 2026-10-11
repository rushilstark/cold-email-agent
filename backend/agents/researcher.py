"""
Pillar II: AI Researcher with MLX Inference & Google OSINT.

Analyses a job listing against Rushil's background and uses Google Custom Search
to find Stony Brook alumni ("Software Engineering Manager" OR "Senior Software Engineer")
on LinkedIn for warmer targets. Uses local Apple MLX inference via OpenAI API.
"""
from __future__ import annotations

import json
import logging
import re
import os
import httpx
from typing import Optional

from openai import AsyncOpenAI
from backend.config import get_settings

logger = logging.getLogger(__name__)

RESUME_SUMMARY = """
RUSHIL REDDY CHIRLA — Software Engineer | Full-Stack & AI/ML
Education: MS CS Stony Brook University (2026-2028)
Experience: 3 years at Fidelity Investments
- Maintained Developer Toolkit platform (500+ API requests/month, 70+ teams)
- Automated 70% of code generation from Swagger to Spring Boot microservices
- Full-stack IDP system: AWS Textract + Python + Angular
Skills: Python, Java, JavaScript, TypeScript, Angular, Node.js, Spring Boot, AWS
"""

# MLX Server Config (Running locally)
MLX_BASE_URL = "http://localhost:8080/v1"
MLX_MODEL_NAME = "mlx-community/Qwen2.5-Coder-7B-Instruct-4bit"

_RESEARCH_PROMPT_TEMPLATE = """\
You are a recruiting intelligence assistant. Analyse the company and role below against the candidate profile.

CANDIDATE PROFILE:
{resume_summary}

COMPANY: {company_name}
ROLE TITLE: {role_title}
ROLE DESCRIPTION:
{role_description}

Perform the following analysis:
1. Extract the exact tech stack required (list individual tools).
2. Infer the company's engineering culture.
3. Identify how the candidate's specific experiences overlap with this role.
4. Identify if they are F-1/visa friendly.

Return ONLY valid JSON with this exact structure:
{{
  "tech_stack": ["list", "of", "technologies"],
  "culture_signals": ["signal 1"],
  "key_responsibilities": ["responsibility 1"],
  "rushil_fit_notes": "2-3 sentence explanation of fit",
  "f1_friendly_signals": ["signals"]
}}
"""

async def _osint_find_alumni(company_name: str) -> Optional[str]:
    """
    Find Stony Brook alumni at the target company using Google Custom Search.
    Targeting: Software Engineering Manager OR Senior Software Engineer
    """
    settings = get_settings()
    # Assume settings has GOOGLE_CSE_ID and GOOGLE_API_KEY
    api_key = getattr(settings, 'GEMINI_API_KEY', os.getenv('GOOGLE_API_KEY'))
    cse_id = os.getenv('GOOGLE_CSE_ID')
    
    if not api_key or not cse_id:
        logger.warning("Google OSINT keys not configured. Skipping alumni search.")
        return None
        
    query = f'site:linkedin.com/in/ "{company_name}" ("Stony Brook" OR "Stony Brook University") ("Software Engineering Manager" OR "Senior Software Engineer" OR "CTO")'
    url = "https://www.googleapis.com/customsearch/v1"
    
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, params={"key": api_key, "cx": cse_id, "q": query})
            resp.raise_for_status()
            data = resp.json()
            
            items = data.get("items", [])
            if items:
                # Return the title and link of the top match
                top_match = items[0]
                return f"{top_match.get('title')} - {top_match.get('link')}"
    except Exception as e:
        logger.error(f"OSINT Search failed for {company_name}: {e}")
        
    return None

def _strip_json_fences(text: str) -> str:
    text = re.sub(r"^```[a-z]*\n?", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    return text.strip()

async def research_company_and_role(
    company_name: str,
    company_website: str,
    role_title: str,
    role_description: str,
) -> dict:
    empty_result = {
        "tech_stack": [],
        "culture_signals": [],
        "key_responsibilities": [],
        "rushil_fit_notes": "Could not research.",
        "founder_accessible": False,
        "f1_friendly_signals": [],
        "osint_alumni_contact": None
    }

    prompt = _RESEARCH_PROMPT_TEMPLATE.format(
        resume_summary=RESUME_SUMMARY,
        company_name=company_name or "Unknown Company",
        role_title=role_title or "Internship",
        role_description=(role_description or "No description provided.")[:2000],
    )

    try:
        client = AsyncOpenAI(base_url=MLX_BASE_URL, api_key="not-needed")
        response = await client.chat.completions.create(
            model=MLX_MODEL_NAME,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=512,
        )
        
        raw = _strip_json_fences(response.choices[0].message.content)
        result = json.loads(raw)
        
        for key in empty_result.keys():
            if key not in result and key != "osint_alumni_contact":
                result[key] = empty_result[key]
                
        # Run OSINT Search concurrently
        alumni_contact = await _osint_find_alumni(company_name)
        result["osint_alumni_contact"] = alumni_contact
        
        # If alumni is found, we assume we have an accessible contact
        if alumni_contact:
            result["founder_accessible"] = True

        return result
    except Exception as exc:
        logger.warning(f"MLX research error for {company_name}: {exc}. Falling back to Gemini 3 Flash...")
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
            logger.error(f"Gemini fallback failed: {gemini_exc}")
            return empty_result
