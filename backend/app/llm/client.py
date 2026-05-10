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


async def chat(
    system_prompt: str,
    user_prompt: str,
    timeout: float = 15.0,
    max_tokens: int = 2000,
    json_mode: bool = True,
) -> dict:
    """Call LLM and parse JSON response. Fast timeout to avoid blocking scans."""
    start = time.monotonic()
    try:
        request = {
            "model": settings.llm_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": max_tokens,
            "timeout": timeout,
        }
        if json_mode:
            request["response_format"] = {"type": "json_object"}

        try:
            response = await client.chat.completions.create(**request)
        except Exception as e:
            if not json_mode or "response_format" not in str(e).lower():
                raise
            logger.warning("LLM JSON mode unsupported, retrying without response_format: %s", e)
            request.pop("response_format", None)
            response = await client.chat.completions.create(**request)

        content = response.choices[0].message.content
        latency_ms = int((time.monotonic() - start) * 1000)

        if not json_mode:
            return {
                "content": content or "",
                "_latency_ms": latency_ms,
                "_model": settings.llm_model,
            }

        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            if "```" in content:
                json_str = content.split("```")[1].strip()
                if json_str.startswith("json"):
                    json_str = json_str[4:].strip()
                result = json.loads(json_str)
            else:
                logger.warning("LLM returned non-JSON: %s", content[:200] if content else "(empty)")
                return {
                    "error": "invalid_json",
                    "action": "reject",
                    "risk_score": 10,
                    "reason": "LLM returned invalid JSON; fail closed",
                    "_latency_ms": latency_ms,
                }

        result["_latency_ms"] = latency_ms
        result["_model"] = settings.llm_model
        return result

    except Exception as e:
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.error("LLM call failed: %s", e)
        return {
            "error": str(e),
            "action": "reject",
            "risk_score": 10,
            "reason": "LLM call failed; fail closed",
            "_latency_ms": latency_ms,
        }
