import time
import httpx
from typing import Dict, Any
from app.core.config import settings
from app.services.llm.base import BaseLLMProvider
from app.services.llm.mock_provider import MockLLMProvider
from app.services.llm.deepseek_provider import DeepSeekProvider
from app.services.llm.claude_provider import ClaudeProvider
from app.services.llm.openai_provider import OpenAIProvider

def get_llm_provider() -> BaseLLMProvider:
    provider_name = settings.LLM_PROVIDER.lower()
    
    if provider_name == "deepseek":
        return DeepSeekProvider()
    elif provider_name == "claude":
        return ClaudeProvider()
    elif provider_name == "openai":
        return OpenAIProvider(base_url="https://api.openai.com/v1", model="gpt-4o-mini")
    elif provider_name == "ollama":
        # Local self-hosted LLM with zero API costs and 100% privacy
        return OpenAIProvider(base_url="http://localhost:11434/v1", model="llama3.3")
    
    # Default: Deterministic local clinical provider
    return MockLLMProvider()

async def check_llm_connectivity() -> Dict[str, Any]:
    """
    Diagnostic tool to verify live connectivity, latency, and status with the configured LLM.
    """
    provider = settings.LLM_PROVIDER.lower()
    start_time = time.time()

    if provider == "mock":
        return {
            "provider": "mock",
            "model": "built-in-deterministic-clinical-engine",
            "status": "ONLINE",
            "latency_ms": round((time.time() - start_time) * 1000, 2),
            "mode": "Offline Local (Zero external dependencies, guaranteed < 5ms)"
        }

    elif provider == "deepseek":
        if not settings.DEEPSEEK_API_KEY:
            return {
                "provider": "deepseek",
                "status": "UNCONFIGURED",
                "error": "DEEPSEEK_API_KEY missing in .env (Auto-falling back to deterministic engine)"
            }
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                res = await client.get(
                    f"{settings.DEEPSEEK_BASE_URL}/models",
                    headers={"Authorization": f"Bearer {settings.DEEPSEEK_API_KEY}"}
                )
                latency = round((time.time() - start_time) * 1000, 2)
                return {
                    "provider": "deepseek",
                    "model": "deepseek-chat (DeepSeek-V3)",
                    "status": "CONNECTED" if res.status_code == 200 else f"ERROR_{res.status_code}",
                    "latency_ms": latency
                }
        except Exception as e:
            return {"provider": "deepseek", "status": "OFFLINE", "error": str(e)}

    elif provider == "claude":
        if not settings.ANTHROPIC_API_KEY:
            return {
                "provider": "claude",
                "status": "UNCONFIGURED",
                "error": "ANTHROPIC_API_KEY missing in .env"
            }
        return {
            "provider": "claude",
            "model": "claude-3-5-haiku-20241022",
            "status": "CONFIGURED",
            "mode": "Active"
        }

    elif provider == "openai":
        if not settings.OPENAI_API_KEY:
            return {
                "provider": "openai",
                "status": "UNCONFIGURED",
                "error": "OPENAI_API_KEY missing in .env"
            }
        return {
            "provider": "openai",
            "model": "gpt-4o-mini",
            "status": "CONFIGURED",
            "mode": "Active"
        }

    elif provider == "ollama":
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                res = await client.get("http://localhost:11434/api/tags")
                latency = round((time.time() - start_time) * 1000, 2)
                return {
                    "provider": "ollama (self-hosted local)",
                    "status": "CONNECTED" if res.status_code == 200 else "ERROR",
                    "latency_ms": latency
                }
        except Exception as e:
            return {
                "provider": "ollama",
                "status": "NOT_RUNNING",
                "note": "Start Ollama locally with `ollama run llama3.3` or use mock/deepseek"
            }

    return {"provider": provider, "status": "UNKNOWN"}
