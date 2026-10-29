"""Single-attempt text-only secondary transport; fixed endpoints, no hidden retries."""

import httpx
from pydantic import SecretStr

OPENROUTER_MODEL = "openai/gpt-oss-120b:free"
ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"


class OpenRouterError(Exception):
    """Fixed public code; no response bodies, headers or credentials retained."""
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _error_code(status):
    if status == 429:
        return "rate_limit_or_quota"
    if status in (408, 504):
        return "timeout"
    if status in (401, 403):
        return "access_denied"
    if status == 404:
        return "model_unavailable"
    if 500 <= status <= 599:
        return "service_busy"
    return "provider_error"


def generate_json(*, api_key: SecretStr, system_prompt: str, message: str, schema: dict,model=None,provider="openrouter") -> str:
    """Return one complete JSON string; caller must apply strict local validation."""
    model=model or OPENROUTER_MODEL
    if "qwen" in model.lower() or provider not in {"openrouter","groq"}:
        raise OpenRouterError("configuration")
    if provider=="openrouter" and not model.endswith(":free"):
        raise OpenRouterError("configuration")
    body = {
        "model": model,
        "messages": [{"role": "system", "content": system_prompt},
                     {"role": "user", "content": message}],
        "temperature": 0, "max_tokens": 8192, "stream": False,
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "shobuj_potro", "strict": True, "schema": schema}},
        "provider": {"require_parameters": True, "allow_fallbacks": False,
                     "max_price": {"prompt": 0, "completion": 0, "request": 0}},
    }
    endpoint=ENDPOINT
    if provider=="groq":
        endpoint="https://api.groq.com/openai/v1/chat/completions"
        del body["provider"]
        if not model.startswith("openai/gpt-oss-"):
            import json
            body["response_format"]={"type":"json_object"}
            body["messages"][0]["content"]+= "\nReturn JSON conforming to this schema: "+json.dumps(schema)
    try:
        # No status retries, redirects or environment proxies. Authorization is
        # sent only to this fixed endpoint; no model lists or response healing.
        with httpx.Client(timeout=60.0, follow_redirects=False, trust_env=False) as client:
            response = client.post(endpoint,
                headers={"Authorization": "Bearer " + api_key.get_secret_value()}, json=body)
        if not 200 <= response.status_code < 300:
            raise OpenRouterError(_error_code(response.status_code))
        data = response.json()
        if not isinstance(data, dict):
            raise OpenRouterError("malformed_response")
        if "error" in data:
            error = data["error"]
            code = error.get("code") if isinstance(error, dict) else None
            raise OpenRouterError(_error_code(code) if type(code) is int else "provider_error")
        if data.get("model") not in (model, model.removesuffix(":free")):
            raise OpenRouterError("malformed_response")
        choices = data.get("choices")
        if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
            raise OpenRouterError("malformed_response")
        choice = choices[0]
        content = choice.get("message")
        if (choice.get("finish_reason") != "stop" or not isinstance(content, dict)
            or content.get("role") != "assistant" or content.get("refusal")
            or content.get("tool_calls") or not isinstance(content.get("content"), str)
            or not content["content"].strip()):
            raise OpenRouterError("malformed_response")
        return content["content"]
    except OpenRouterError:
        raise
    except (httpx.TimeoutException, TimeoutError):
        raise OpenRouterError("timeout") from None
    except httpx.TransportError:
        raise OpenRouterError("network_error") from None
    except (ValueError, TypeError):
        raise OpenRouterError("malformed_response") from None
    except Exception:
        raise OpenRouterError("unexpected") from None
