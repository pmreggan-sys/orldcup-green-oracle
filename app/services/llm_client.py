from __future__ import annotations

from dataclasses import dataclass

import httpx
import json as jsonlib

from app.config import Settings


class LLMError(RuntimeError):
    """Raised when the upstream provider fails or returns invalid content."""


@dataclass(slots=True)
class OpenAICompatibleClient:
    settings: Settings

    async def chat_json(self, system_prompt: str, user_prompt: str, *, model: str | None = None) -> dict:
        if self.settings.openai_api_key.strip():
            return await self._chat_openai_json(system_prompt, user_prompt, model=model)
        if self.settings.anthropic_auth_token.strip():
            return await self._chat_anthropic_json(system_prompt, user_prompt, model=model)
        raise LLMError("No configured text-generation provider is available.")

    async def _chat_openai_json(self, system_prompt: str, user_prompt: str, *, model: str | None = None) -> dict:
        payload = {
            "model": model or self.settings.openai_model,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        url = f"{self.settings.openai_base_url.rstrip('/')}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(self.settings.request_timeout_s)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
        if response.status_code >= 400:
            raise LLMError(f"Upstream provider returned {response.status_code}: {response.text[:200]}")
        data = self._decode_top_level_payload(response)
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Upstream provider returned an unexpected payload.") from exc
        if not content:
            raise LLMError("Upstream provider returned an empty message.")
        return self._decode_message_content(content)

    async def _chat_anthropic_json(self, system_prompt: str, user_prompt: str, *, model: str | None = None) -> dict:
        payload = {
            "model": model or self.settings.anthropic_model,
            "max_tokens": 1200,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": user_prompt},
            ],
        }
        url = f"{self.settings.anthropic_base_url.rstrip('/')}/v1/messages"
        headers = {
            "x-api-key": self.settings.anthropic_auth_token,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        if self.settings.claude_code_disable_nonessential_traffic:
            headers["x-claude-code-disable-nonessential-traffic"] = "1"
        if self.settings.claude_code_attribution_header.strip():
            headers["x-claude-code-attribution-header"] = self.settings.claude_code_attribution_header.strip()
        timeout = httpx.Timeout(self.settings.request_timeout_s)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(url, headers=headers, json=payload)
        if response.status_code >= 400:
            raise LLMError(f"Upstream provider returned {response.status_code}: {response.text[:200]}")
        data = self._decode_top_level_payload(response)
        try:
            content_blocks = data["content"]
            text_parts = [block["text"] for block in content_blocks if isinstance(block, dict) and block.get("type") == "text"]
            content = "\n".join(text_parts).strip()
        except (KeyError, TypeError) as exc:
            raise LLMError("Anthropic-compatible provider returned an unexpected payload.") from exc
        if not content:
            raise LLMError("Anthropic-compatible provider returned an empty message.")
        return self._decode_message_content(content)

    @staticmethod
    def _decode_top_level_payload(response: httpx.Response) -> dict:
        content_type = response.headers.get("content-type", "")
        text = response.text.strip()
        if "application/json" in content_type or text.startswith("{") or text.startswith("["):
            try:
                return response.json()
            except ValueError as exc:
                raise LLMError("Upstream provider returned invalid JSON.") from exc
        if text.startswith("<!doctype html") or text.startswith("<html"):
            raise LLMError("Upstream provider returned an HTML page instead of a chat-completions JSON payload.")
        raise LLMError("Upstream provider returned an unsupported top-level payload format.")

    @staticmethod
    def _decode_message_content(content: str) -> dict:
        stripped = content.strip()
        if stripped.startswith("```"):
            stripped = OpenAICompatibleClient._strip_markdown_fence(stripped)
        try:
            return jsonlib.loads(stripped)
        except ValueError as exc:
            raise LLMError("Upstream provider returned non-JSON content.") from exc

    @staticmethod
    def _strip_markdown_fence(content: str) -> str:
        lines = content.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
            return "\n".join(lines[1:-1]).strip()
        return content
