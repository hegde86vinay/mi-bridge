from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import Any

from models import IncidentContext
from utils.llm_client import LLMClient
from utils.logger import log


class BaseAgent(ABC):
    name: str = "BASE"

    def __init__(self, llm: LLMClient, tools: dict[str, Any]) -> None:
        self.llm = llm
        self.tools = tools

    @abstractmethod
    async def run(self, ctx: IncidentContext) -> None:
        """Execute the agent's work, writing results into ctx."""
        ...

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Call the LLM and parse JSON response, with one retry on parse failure."""
        raw = await self.llm.complete(system_prompt, user_prompt, self.name)
        result, ok = self._try_parse_json(raw)
        if ok:
            self._log("JSON parse succeeded")
            return result

        # First attempt failed — retry with a corrective prefix
        self._log("JSON parse failed — retrying with correction prompt")
        retry_user = (
            "Your previous response was not valid JSON. "
            "Return ONLY valid JSON with no markdown fences, no explanation:\n\n"
            + user_prompt
        )
        raw2 = await self.llm.complete(system_prompt, retry_user, self.name)
        result2, ok2 = self._try_parse_json(raw2)
        if ok2:
            self._log("JSON parse succeeded on retry")
            return result2

        raise RuntimeError(
            f"[{self.name}] JSON parse failed on both attempts. "
            f"Last raw response:\n{raw2}"
        )

    @staticmethod
    def _try_parse_json(raw: str) -> tuple[dict[str, Any], bool]:
        """Strip markdown fences and try json.loads. Returns (result, success)."""
        cleaned = raw.strip()
        # Remove optional ```json ... ``` fences
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            # Drop first line (```json or ```) and last line (```)
            cleaned = "\n".join(lines[1:-1]).strip()
        try:
            return json.loads(cleaned), True
        except json.JSONDecodeError:
            return {}, False

    def _log(self, message: str) -> None:
        log(self.name, message)
