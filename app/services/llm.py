from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from functools import lru_cache
from pathlib import Path
from threading import Lock
from typing import TYPE_CHECKING, Any

from app.config import get_settings

if TYPE_CHECKING:
    from app.models.message import Message


class LocalLlmService:
    """Generate assistant replies with a local GGUF-backed model."""

    def __init__(self, *, gguf_path: Path) -> None:
        self._gguf_path = gguf_path
        self._model = self._load_model(gguf_path)
        self._generation_lock = Lock()

    async def generate_reply(self, *, messages: list[Message]) -> str:
        """Generate the next assistant reply without blocking the event loop."""
        return await asyncio.to_thread(self._generate_reply_sync, messages)

    async def stream_reply(self, *, messages: list[Message]) -> AsyncIterator[str]:
        """Yield the next assistant reply token by token without blocking the event loop."""
        queue: asyncio.Queue[str | Exception | object] = asyncio.Queue()
        loop = asyncio.get_running_loop()
        sentinel = object()

        def _producer() -> None:
            try:
                for token in self._stream_reply_sync(messages=messages):
                    loop.call_soon_threadsafe(queue.put_nowait, token)
            except Exception as error:
                loop.call_soon_threadsafe(queue.put_nowait, error)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, sentinel)

        producer_task = asyncio.create_task(asyncio.to_thread(_producer))
        try:
            while True:
                item = await queue.get()
                if item is sentinel:
                    break
                if isinstance(item, Exception):
                    raise item

                yield item
        finally:
            await producer_task

    def _generate_reply_sync(self, messages: list[Message]) -> str:
        """Generate the next assistant reply for the conversation."""
        reply = ''.join(self._stream_reply_sync(messages=messages)).strip()
        if reply:
            return reply

        msg = 'The local model returned an empty response.'
        raise RuntimeError(msg)

    def _stream_reply_sync(self, *, messages: list[Message]) -> Iterator[str]:
        """Yield the next assistant reply token by token."""
        prompt_text = self._build_prompt(messages=messages)
        try:
            with self._generation_lock:
                response_stream = self._model.create_completion(
                    prompt_text,
                    max_tokens=512,
                    temperature=0.7,
                    stop=['\nUser:', '\nSystem:'],
                    stream=True,
                )
                for chunk in response_stream:
                    token = chunk['choices'][0]['text']
                    if token:
                        yield token
        except Exception as error:
            msg = f'Failed to generate a reply with the local GGUF model: {error}'
            raise RuntimeError(msg) from error

    def _load_model(self, gguf_path: Path) -> Any:
        if not gguf_path.is_file():
            msg = f'Configured GGUF file does not exist: {gguf_path}'
            raise RuntimeError(msg)

        try:
            from llama_cpp import Llama
        except ImportError as error:
            msg = (
                'The `llama-cpp-python` package is required for GGUF chat generation, '
                'but it is not installed in the current environment.'
            )
            raise RuntimeError(msg) from error

        try:
            return Llama(model_path=str(gguf_path), verbose=False)
        except Exception as error:
            msg = f'Failed to load the local GGUF model from {gguf_path}: {error}'
            raise RuntimeError(msg) from error

    def _build_prompt(self, *, messages: list[Message]) -> str:
        history_lines = [
            'System: You are a helpful assistant. Answer clearly and concisely.',
        ]
        for message in messages:
            history_lines.append(f'{self._role_name(message.role)}: {message.content.strip()}')

        history_lines.append('Assistant:')
        return '\n\n'.join(history_lines)

    @staticmethod
    def _role_name(role: str) -> str:
        if role == 'assistant':
            return 'Assistant'
        if role == 'system':
            return 'System'

        return 'User'


@lru_cache(maxsize=1)
def get_llm_service() -> LocalLlmService:
    """Return a cached local LLM service instance."""
    settings = get_settings()
    return LocalLlmService(gguf_path=settings.llm.gguf_path)
