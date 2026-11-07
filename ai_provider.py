# -*- coding: utf-8 -*-
"""Server-side DeepSeek (OpenAI-compatible) client for the AI Teacher Assistant.

The API key is read ONLY on the server, in this priority order:
    1. DEEPSEEK_API_KEY environment variable
    2. TEACHFLOW_AI_KEY environment variable (legacy)
    3. deepseek_api_key stored in the app's settings table (set by an admin)
It is NEVER sent to the browser. All calls go through the OpenAI-compatible
/chat/completions endpoint, so the provider (DeepSeek -> any OpenAI-compatible
service) can be swapped by changing DEEPSEEK_BASE_URL / DEEPSEEK_MODEL.
"""
import os
import json
import urllib.request
import urllib.error

from db import get_setting

DEFAULT_BASE = "https://api.deepseek.com/v1"
DEFAULT_MODEL = "deepseek-chat"


def api_key():
    return (
        os.environ.get("DEEPSEEK_API_KEY")
        or os.environ.get("TEACHFLOW_AI_KEY")
        or os.environ.get("OPENAI_API_KEY")
        or get_setting("deepseek_api_key")
    )


def base_url():
    return os.environ.get("DEEPSEEK_BASE_URL", DEFAULT_BASE).rstrip("/")


def model():
    return os.environ.get("DEEPSEEK_MODEL") or get_setting("deepseek_model") or DEFAULT_MODEL


def configured():
    return bool(api_key())


def _request(payload, timeout=120):
    req = urllib.request.Request(
        base_url() + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer " + api_key(),
        },
    )
    return urllib.request.urlopen(req, timeout=timeout)


def complete(messages, max_tokens=2000, temperature=0.7):
    """Non-streaming completion. Returns the assistant text, or raises."""
    if not configured():
        raise RuntimeError("no_key")
    payload = {
        "model": model(),
        "messages": messages,
        "stream": False,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    with _request(payload) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    return (data["choices"][0]["message"]["content"] or "").strip()


def stream_chat(messages, max_tokens=2000, temperature=0.7):
    """Generator yielding text deltas from a streaming completion."""
    if not configured():
        raise RuntimeError("no_key")
    payload = {
        "model": model(),
        "messages": messages,
        "stream": True,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    with _request(payload) as resp:
        for raw in resp:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                break
            try:
                obj = json.loads(data)
            except ValueError:
                continue
            choices = obj.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            piece = delta.get("content")
            if piece:
                yield piece
