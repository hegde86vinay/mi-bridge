from __future__ import annotations

import time

import anthropic

from utils.logger import log


class LLMClient:
    """Thin async wrapper around anthropic.AsyncAnthropic."""

    model = "claude-3-5-sonnet-20241022"
    max_tokens = 2048

    def __init__(self, api_key: str) -> None:
        self.client = anthropic.AsyncAnthropic(api_key=api_key)
        self._api_key = api_key

    async def complete(self, system: str, user: str, agent_name: str = "LLM") -> str:
        log(agent_name, f"→ LLM call  model={self.model}  prompt_chars={len(user)}")
        t0 = time.perf_counter()
        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.AuthenticationError as exc:
            log(
                "ERROR",
                f"Authentication failed for {agent_name} — "
                f"key starts with '{self._api_key[:12]}...'. "
                f"Run with --check-key to diagnose. Original error: {exc}",
            )
            raise
        except anthropic.APIError as exc:
            log("ERROR", f"Anthropic API error in {agent_name}: {exc}")
            raise

        latency = time.perf_counter() - t0
        usage = response.usage
        log(
            agent_name,
            f"← LLM done  in={usage.input_tokens} out={usage.output_tokens} "
            f"latency={latency:.2f}s",
        )
        return response.content[0].text

    async def check_key(self) -> tuple[bool, str]:
        """Probe the API with a minimal request. Returns (ok, message)."""
        try:
            await self.client.messages.create(
                model=self.model,
                max_tokens=5,
                messages=[{"role": "user", "content": "hi"}],
            )
            return True, "API key is valid and working."
        except anthropic.AuthenticationError as exc:
            return False, f"Authentication error: {exc}"
        except anthropic.APIError as exc:
            return False, f"API error (key may be valid but another issue occurred): {exc}"


class DryRunLLMClient:
    """Fake LLM client for --dry-run mode.

    Returns pre-baked realistic JSON responses keyed by agent name,
    with a simulated 0.5 s latency so the parallel phase timing is visible.
    """

    model = "dry-run (no API call)"

    def __init__(self) -> None:
        from utils.dry_run_responses import DRY_RUN_RESPONSES
        self._responses = DRY_RUN_RESPONSES

    async def complete(self, system: str, user: str, agent_name: str = "LLM") -> str:
        import asyncio
        log(agent_name, f"→ DRY-RUN LLM call  (no real API call)  agent={agent_name}")
        await asyncio.sleep(0.5)  # simulate network round-trip; keeps parallel timing realistic

        response = self._responses.get(agent_name)
        if response is None:
            raise RuntimeError(
                f"DryRunLLMClient: no pre-baked response for agent '{agent_name}'. "
                f"Known agents: {list(self._responses.keys())}"
            )

        log(agent_name, f"← DRY-RUN done  chars={len(response)}  (pre-baked response)")
        return response
