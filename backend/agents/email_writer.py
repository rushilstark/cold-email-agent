"""
Hyper-personalized cold email generator powered by Gemini 3.6 Flash / MLX.

Generates subject, body, and personalization notes for a given internship or SWE listing.
Supports CPT mention strategies and specific CTA for Summer 2027 CPT internship openings.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

from backend.config import get_settings

logger = logging.getLogger(__name__)

RESUME_SUMMARY = """
RUSHIL REDDY CHIRLA — Software Engineer | Full-Stack & AI/ML
Education: MS CS Stony Brook University (2026-2028)
Experience: 3 years at Fidelity Investments
- Maintained Developer Toolkit platform (500+ API requests/month, 70+ teams)
- Automated 70% of code generation from Swagger to Spring Boot microservices
- Full-stack IDP system: AWS Textract + Python + Angular, 1000+ docs/month
Skills: Python, Java, JavaScript, TypeScript, Angular, Node.js, Spring Boot, AWS, Docker, AI/ML
"""

CPT_SENTENCES: dict[str, str] = {
    "natural": (
        "I'm pursuing my MS in Computer Science at Stony Brook University "
        "and seeking a Summer 2027 CPT software engineering internship."
    ),
    "explicit": (
        "I have full CPT authorization for Summer 2027 — zero visa sponsorship or paperwork required from your side."
    ),
    "hidden": "",
}

_SYSTEM_PROMPT = f"""\
You are helping Rushil Reddy Chirla write a hyper-personalized cold email to engineering leads or recruiters for a Summer 2027 CPT Software Engineering Internship.
CANDIDATE BACKGROUND:
{RESUME_SUMMARY}
"""

_USER_PROMPT_TEMPLATE = """\
COMPANY: {company_name}
POSTED ROLE: {role_title}
ROLE DESCRIPTION: {role_description}
COMPANY TECH STACK: {tech_stack}
RECIPIENT NAME: {recipient_name}
CPT STATEMENT: {cpt_sentence}

STRICT WRITE RULES:
1. **Salutation**: "Hi {recipient_first_name}," (or "Hi there," if name is unknown)
2. **Subject line**: 6-9 words. Specific to what the company builds + Summer 2027 SWE Intern. (e.g. "Summer 2027 SWE Intern — 3yrs Spring Boot & AI experience")
3. **Opening Hook**: 1 sentence connecting Rushil's exact background (3 yrs SWE at Fidelity, 70% automation, 500+ APIs) to what THIS company builds in {role_title}. Do NOT say "I came across your job posting" or "I was impressed by your work".
4. **Body**: 2 short paragraphs (120-160 words max).
   - Paragraph 1: Highlighting production engineering experience (Spring Boot, Angular, AWS Textract, microservices).
   - Paragraph 2: Mention CPT status: "{cpt_sentence}".
5. **Call To Action (CTA)**: Ask directly to be interviewed / considered for a Summer 2027 CPT internship:
   "Would you be open to interviewing me for a Summer 2027 CPT software engineering intern role on your team?" OR "Are you open to considering me for a Summer 2027 CPT internship interview?"
6. **Sign off**:
   Best,
   Rushil Reddy Chirla
   MS CS, Stony Brook University | 3 yrs SWE at Fidelity
   rushil.chirla@gmail.com

Return ONLY valid JSON (no markdown formatting):
{{
  "subject": "...",
  "body": "...",
  "personalization_notes": "1 sentence explaining why this angle fits the role"
}}
"""

def _strip_json_fences(text: str) -> str:
    text = re.sub(r"^```[a-z]*\n?", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"```\s*$", "", text, flags=re.MULTILINE)
    return text.strip()


async def generate_email(
    listing: dict,
    profile: dict,
    cpt_strategy: str = "natural",
    recipient_type: str = "unknown",
    recipient_name: str = "",
) -> dict:
    company_name = listing.get("company_name") or "Your Team"
    role_title = listing.get("role_title") or "Software Engineer"
    recipient_first_name = recipient_name.split()[0] if recipient_name and recipient_name != "None" else "there"
    cpt_sentence = CPT_SENTENCES.get(cpt_strategy, CPT_SENTENCES["natural"])

    fallback: dict = {
        "subject": f"Summer 2027 SWE Intern — 3 yrs SWE at Fidelity / MS CS Stony Brook",
        "body": (
            f"Hi {recipient_first_name},\n\n"
            f"I saw {company_name} is hiring for {role_title}. With 3 years of full-stack experience at Fidelity Investments—where I automated 70% of microservice code generation and scaled IDP pipelines serving 500+ API requests/month—I'd love to bring this production engineering experience to your team.\n\n"
            f"{cpt_sentence} Would you be open to interviewing me for a Summer 2027 CPT software engineering intern role on your team?\n\n"
            f"Best,\n"
            f"Rushil Reddy Chirla\n"
            f"MS CS Student @ Stony Brook University | Ex-Fidelity Software Engineer\n"
            f"rushil.chirla@gmail.com"
        ),
        "personalization_notes": f"Cold pitch tailored for {company_name} - {role_title}",
    }

    tech_stack_str = ", ".join(profile.get("tech_stack") or []) or "Python, Java, Spring Boot, AWS"

    user_prompt = _USER_PROMPT_TEMPLATE.format(
        company_name=company_name,
        role_title=role_title,
        role_description=(listing.get("role_description") or role_title)[:1500],
        tech_stack=tech_stack_str,
        recipient_name=recipient_name or "there",
        recipient_first_name=recipient_first_name,
        cpt_sentence=cpt_sentence,
    )

    # Primary: google-genai with gemini-3.6-flash
    try:
        from google import genai
        settings = get_settings()
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=_SYSTEM_PROMPT + "\n\n" + user_prompt,
        )
        raw = _strip_json_fences(response.text)
        result = json.loads(raw)
        for key in ("subject", "body", "personalization_notes"):
            if key not in result or not result[key]:
                raise ValueError(f"Missing key: {key}")
        return result

    except Exception as exc:
        logger.warning(f"Gemini generation failed: {exc}. Trying local MLX fallback...")
        try:
            from openai import AsyncOpenAI
            mlx_client = AsyncOpenAI(base_url="http://localhost:8080/v1", api_key="not-needed")
            resp = await mlx_client.chat.completions.create(
                model="mlx-community/Qwen2.5-Coder-7B-Instruct-4bit",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.4,
                max_tokens=1024,
            )
            raw = _strip_json_fences(resp.choices[0].message.content)
            result = json.loads(raw)
            return result
        except Exception as mlx_exc:
            logger.error(f"MLX fallback also failed: {mlx_exc}")
            return fallback
