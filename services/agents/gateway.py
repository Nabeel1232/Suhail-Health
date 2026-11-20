"""Official Groq SDK gateway with replayable, atomic spending reservations.

No provider built-in tools, streaming, MCP or code execution are exposed.
The append-only call ledger stores permitted synthetic/public input only.
"""
from __future__ import annotations

import asyncio
import fcntl
import hashlib
import json
import os
import random
import re
import sqlite3
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import jsonschema
from dotenv import dotenv_values
from groq import AsyncGroq, APIConnectionError, APIStatusError, APITimeoutError

ROOT = Path(__file__).resolve().parents[2]
PRICE_MAP = {"version": "groq-models-2026-11-15", "source": "https://console.groq.com/docs/models",
             "models": {"openai/gpt-oss-120b": [0.15, 0.60], "openai/gpt-oss-20b": [0.075, 0.30]}}


def utcnow():
    return datetime.now(timezone.utc).isoformat()


def env_value(name: str, default=None):
    """Read a required setting, preserving process environment precedence."""
    if name in os.environ:
        return os.environ[name]
    owner = Path(os.environ.get("ENV_FILE_PATH", os.environ.get("ENV_FILE", str(ROOT / ".env"))))
    private = dotenv_values(owner) if owner.is_file() else {}
    if name == "GROQ_API_KEY":
        candidate = private.get(name) or private.get("grok-api")
        return candidate if candidate and (private.get(name) or candidate.startswith("gsk_")) else default
    return private.get(name) or default


def redact(value):
    text = json.dumps(value, ensure_ascii=False, default=str)
    text = re.sub(r"gsk_[A-Za-z0-9_-]+|xai-[A-Za-z0-9_-]+", "[REDACTED]", text)
    return json.loads(text)


class GatewayError(Exception):
    def __init__(self, code, message, call_id=None):
        self.code, self.message, self.call_id = code, message, call_id
        super().__init__(message)


class GroqGateway:
    def __init__(self, run_dir=None, model=None, max_calls=300, max_tokens=300000, usd_cap=None,
                 timeout=35.0, retries=2, concurrency=2, client=None):
        self.run_dir = Path(run_dir or ROOT / "runtime" / "agent-live")
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self.model = model or env_value("GROQ_MODEL", "openai/gpt-oss-120b")
        self.max_calls = min(int(max_calls), int(env_value("GROQ_MAX_CALLS", max_calls)))
        self.max_tokens = min(int(max_tokens), int(env_value("GROQ_MAX_TOKENS", max_tokens)))
        self.usd_cap = usd_cap if usd_cap is not None else env_value("GROQ_USD_CAP")
        self.usd_cap = float(self.usd_cap) if self.usd_cap not in (None, "") else None
        self.timeout, self.retries = timeout, min(int(retries), 3)
        self.semaphore = asyncio.Semaphore(min(int(concurrency), 2))
        self.key = env_value("GROQ_API_KEY")
        self.client = client or (AsyncGroq(api_key=self.key, timeout=timeout, max_retries=0) if self.key else None)
        self.db_path = self.run_dir / "budget.sqlite3"
        self.ledger_path = self.run_dir / "provider-calls.jsonl"
        with self.db() as db:
            db.execute("CREATE TABLE IF NOT EXISTS reservations (id TEXT PRIMARY KEY, tokens INTEGER NOT NULL, actual INTEGER, cost REAL, state TEXT NOT NULL)")
            db.execute("CREATE TABLE IF NOT EXISTS run_config (id INTEGER PRIMARY KEY CHECK(id=1), model TEXT, max_calls INTEGER, max_tokens INTEGER)")
            cfg = db.execute("SELECT model,max_calls,max_tokens FROM run_config WHERE id=1").fetchone()
            current = (self.model, self.max_calls, self.max_tokens)
            if cfg and tuple(cfg) != current:
                raise GatewayError("run_configuration_conflict", "A model or budget change requires a new run directory.")
            db.execute("INSERT OR IGNORE INTO run_config VALUES (1,?,?,?)", current)

    def db(self):
        db = sqlite3.connect(self.db_path, timeout=30)
        db.execute("PRAGMA busy_timeout=30000")
        return db

    def reserve(self, worst_tokens):
        if not self.client:
            raise GatewayError("missing_credentials", "Groq credential is unavailable; fixed templates remain available.")
        if self.usd_cap is not None and self.model not in PRICE_MAP["models"]:
            raise GatewayError("budget_configuration_blocked", "USD cap needs a dated verified price map for this exact model.")
        rid = str(uuid.uuid4())
        with self.db() as db:
            db.execute("BEGIN IMMEDIATE")
            calls, tokens, cost = db.execute("SELECT COUNT(*),COALESCE(SUM(COALESCE(actual,tokens)),0),COALESCE(SUM(cost),0) FROM reservations").fetchone()
            if calls >= self.max_calls or tokens + worst_tokens > self.max_tokens:
                raise GatewayError("budget_exhausted", "The configured request or conservative token allowance is exhausted.")
            if self.usd_cap is not None:
                rate = max(PRICE_MAP["models"][self.model])
                unknown = db.execute("SELECT COALESCE(SUM(tokens),0) FROM reservations WHERE cost IS NULL").fetchone()[0]
                if cost + (unknown + worst_tokens) * rate / 1e6 > self.usd_cap:
                    raise GatewayError("budget_exhausted", "The configured conservative currency allowance is exhausted.")
            db.execute("INSERT INTO reservations VALUES (?,?,NULL,NULL,'reserved')", (rid, worst_tokens))
        return rid

    def finish(self, rid, usage, status):
        cost = None
        total = None
        if usage:
            total = usage["total_tokens"]
            rates = PRICE_MAP["models"].get(self.model)
            if rates:
                cost = (usage["input_tokens"] * rates[0] + usage["output_tokens"] * rates[1]) / 1e6
        with self.db() as db:
            db.execute("UPDATE reservations SET actual=?,cost=?,state=? WHERE id=?", (total, cost, status, rid))
        return cost

    def append(self, record):
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        with self.ledger_path.open("a+", encoding="utf-8") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            f.seek(0)
            lines = f.read().splitlines()
            record = redact(record)
            record["previous_hash"] = json.loads(lines[-1])["record_hash"] if lines else None
            record["record_hash"] = hashlib.sha256(json.dumps(record, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            os.fsync(f.fileno())
            fcntl.flock(f, fcntl.LOCK_UN)

    def budget_status(self):
        with self.db() as db:
            calls, charged, known, unknown, cost = db.execute("SELECT COUNT(*),COALESCE(SUM(COALESCE(actual,tokens)),0),COALESCE(SUM(actual),0),SUM(CASE WHEN actual IS NULL THEN 1 ELSE 0 END),SUM(cost) FROM reservations").fetchone()
        return {"max_calls": self.max_calls, "max_tokens": self.max_tokens, "api_calls": calls,
                "charged_tokens": charged, "known_actual_tokens": known, "unknown_usage_calls": unknown or 0,
                "cost_usd": cost if not unknown else None, "usd_cap": self.usd_cap,
                "price_map_version": PRICE_MAP["version"]}

    async def complete(self, messages, response_schema=None, tools=None, mode="structured", max_tokens=2048, metadata=None, tool_choice="auto"):
        if mode not in {"structured", "tool", "text"}:
            raise GatewayError("invalid_mode", "Unsupported inference mode.")
        if response_schema is not None and (tools or mode == "tool"):
            raise GatewayError("incompatible_modes", "Structured Outputs cannot be combined with tools.")
        if mode == "structured" and response_schema is None:
            raise GatewayError("schema_required", "Structured mode requires a server-owned schema.")
        if tools and any(t.get("type") != "function" for t in tools):
            raise GatewayError("tool_denied", "Only allowlisted local function tools are permitted.")
        max_tokens = min(int(max_tokens), int(env_value("AGENT_MAX_OUTPUT_TOKENS", max_tokens)))
        encoded = json.dumps(messages, ensure_ascii=False).encode()
        if len(encoded) > 100000:
            raise GatewayError("context_budget_exhausted", "Input exceeds this application's bounded context allowance.")
        worst_tokens = len(encoded) + len(json.dumps(response_schema or tools or {})) + int(max_tokens) + 512
        params = {"model": self.model, "messages": messages, "temperature": 0, "max_completion_tokens": int(max_tokens), "stream": False}
        if response_schema is not None:
            params["response_format"] = {"type": "json_schema", "json_schema": {"name": "suhail_proposal", "strict": True, "schema": response_schema}}
        if tools:
            params.update(tools=tools, parallel_tool_calls=False, tool_choice=tool_choice)
        last = None
        async with self.semaphore:
            for attempt in range(self.retries + 1):
                cid = self.reserve(worst_tokens)
                started = time.monotonic()
                base = {"call_id": cid, "timestamp": utcnow(), "model": self.model, "provider": "groq", "mode": mode,
                        "metadata": metadata or {}, "attempt": attempt + 1,
                        "parameters": {k: v for k, v in params.items() if k not in {"messages", "tools", "response_format"}},
                        "messages": messages, "input_hash": hashlib.sha256(encoded).hexdigest(),
                        "schema_hash": hashlib.sha256(json.dumps(response_schema, sort_keys=True).encode()).hexdigest() if response_schema else None,
                        "reserved_tokens": worst_tokens}
                usage = None
                try:
                    response = await self.client.chat.completions.create(**params)
                    msg = response.choices[0].message
                    if response.usage:
                        usage = {"input_tokens": response.usage.prompt_tokens, "output_tokens": response.usage.completion_tokens,
                                 "total_tokens": response.usage.total_tokens}
                    content = msg.content or ""
                    tc = [t.model_dump(exclude_none=True) for t in (msg.tool_calls or [])]
                    parsed = None
                    if response_schema:
                        parsed = json.loads(content)
                        jsonschema.validate(parsed, response_schema)
                    latency = (time.monotonic() - started) * 1000
                    raw_message = {"role": "assistant", "content": content}
                    if tc:
                        raw_message["tool_calls"] = tc
                    cost = self.finish(cid, usage, "completed")
                    result = {"text": content, "parsed": parsed, "call_id": cid, "model": response.model,
                              "usage": usage, "latency_ms": latency, "tool_calls": tc, "raw_message": raw_message}
                    self.append({**base, **result, "status": "completed", "cost_usd": cost, "price_map_version": PRICE_MAP["version"]})
                    return result
                except asyncio.CancelledError:
                    self.finish(cid, usage, "cancelled")
                    self.append({**base, "status": "cancelled", "usage": usage, "error_code": "cancelled", "latency_ms": (time.monotonic()-started)*1000})
                    raise
                except Exception as exc:
                    status = getattr(exc, "status_code", None)
                    code = ("authentication_failed" if status in (401, 403) else "rate_limited" if status == 429 else
                            "model_unavailable" if status == 404 else "invalid_output" if isinstance(exc, (ValueError, jsonschema.ValidationError)) else
                            "timeout" if isinstance(exc, (APITimeoutError, asyncio.TimeoutError)) else "provider_error")
                    # Never persist raw provider error bodies or request headers.
                    cost = self.finish(cid, usage, "failed")
                    self.append({**base, "status": "failed", "usage": usage, "cost_usd": cost, "error_code": code,
                                 "http_status": status, "error": "Groq request failed: " + code,
                                 "latency_ms": (time.monotonic()-started)*1000})
                    last = GatewayError(code, "Groq request failed: " + code, cid)
                    retryable = status == 429 or (status is not None and status >= 500) or isinstance(exc, (APIConnectionError, APITimeoutError))
                    if not retryable or attempt == self.retries:
                        raise last from None
                    retry_after = getattr(getattr(exc, "response", None), "headers", {}).get("retry-after")
                    try:
                        delay = float(retry_after) if retry_after else 0.8 * (2 ** attempt) + random.uniform(0, 0.3)
                    except (ValueError, TypeError):
                        delay = 0.8 * (2 ** attempt)
                    if delay > 45:
                        raise GatewayError("rate_limited", "Provider retry window exceeds bounded interactive wait; retry this run later.", cid) from None
                    await asyncio.sleep(max(0, delay))
        raise last or GatewayError("provider_error", "Groq request did not complete.")

    async def probe(self):
        if not self.client:
            raise GatewayError("missing_credentials", "No server-side Groq credential is configured.")
        cid = self.reserve(0)
        started = time.monotonic()
        zero_usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}
        try:
            available = [m.id for m in (await self.client.models.list()).data]
            self.finish(cid, zero_usage, "completed")
            self.append({"call_id": cid, "timestamp": utcnow(), "provider": "groq", "model": self.model,
                         "mode": "model_list", "status": "completed", "metadata": {"purpose": "capability_probe", "case_id": "probe-model-list"},
                         "usage": zero_usage, "cost_usd": 0, "candidate_models_available": [m for m in available if m in ("openai/gpt-oss-120b", "openai/gpt-oss-20b")],
                         "latency_ms": (time.monotonic()-started)*1000})
        except Exception:
            self.finish(cid, zero_usage, "failed")
            self.append({"call_id": cid, "timestamp": utcnow(), "provider": "groq", "model": self.model,
                         "mode": "model_list", "status": "failed", "metadata": {"purpose": "capability_probe", "case_id": "probe-model-list"},
                         "usage": zero_usage, "cost_usd": 0, "error_code": "provider_error", "error": "Model listing failed.",
                         "latency_ms": (time.monotonic()-started)*1000})
            raise GatewayError("provider_error", "Groq model access probe failed.", cid) from None
        if self.model not in available:
            raise GatewayError("model_unavailable", "The explicitly selected model is unavailable to this account.")
        schema = {"type": "object", "properties": {"synthetic": {"type": "boolean"}}, "required": ["synthetic"], "additionalProperties": False}
        check = await self.complete([{"role": "user", "content": "Return synthetic true for this synthetic capability check."}], response_schema=schema, max_tokens=128,
                                    metadata={"purpose": "capability_probe", "case_id": "probe-structured"})
        return {"selected_model": self.model, "available_candidates": [m for m in available if m in ("openai/gpt-oss-120b", "openai/gpt-oss-20b")], "structured_call_id": check["call_id"], "synthetic": check["parsed"]["synthetic"]}
