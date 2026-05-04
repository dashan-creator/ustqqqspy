from __future__ import annotations

import json
import logging
import time

from openai import AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

client = AsyncOpenAI(
    base_url=settings.llm_base_url,
    api_key=settings.llm_api_key,
)


async def chat(system_prompt: str, user_prompt: str, timeout: float = 30.0) -> dict:
    """Call LLM and parse JSON response."""
    start = time.monotonic()
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.1,
            timeout=timeout,
        )
        content = response.choices[0].message.content
        latency_ms = int((time.monotonic() - start) * 1000)

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            if "```" in content:
                json_str = content.split("```")[1].strip()
                if json_str.startswith("json"):
                    json_str = json_str[4:].strip()
                result = json.loads(json_str)
            else:
                logger.warning("LLM returned non-JSON: %s", content[:200])
                return {"error": "invalid_json", "raw": content[:500], "_latency_ms": latency_ms}

        result["_latency_ms"] = latency_ms
        result["_model"] = settings.llm_model
        return result

    except Exception as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.error("LLM call failed: %s", e)
        return {"error": str(e), "_latency_ms": latency_ms}
