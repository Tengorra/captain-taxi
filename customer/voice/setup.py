"""
ElevenLabs Agents — provisioning script.

Idempotently creates / updates:
  1. Six webhook tools (one per tool defined in agent_config.json)
  2. The Captain Taxi voice agent, wired to those tools
  3. Prints the assistant + tool IDs so you can copy them to .env

Pre-reqs:
    pip install httpx
    export ELEVENLABS_API_KEY=...           # workspace API key
    export ELEVENLABS_WEBHOOK_SECRET=...    # any random 32+ char string
    # Optionally:
    export VOICE_BASE_URL=https://customer.captain.taxi
    export ELEVENLABS_AUTH_HEADER=X-Captain-Auth

Run:
    python -m customer.voice.setup
    # or
    cd customer && python voice/setup.py

The ElevenLabs API is still evolving. If a request fails with a 4xx,
the script prints the exact payload it sent so you can adjust the JSON
in agent_config.json or finish the setup in the dashboard manually.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
from typing import Any

import httpx

API_BASE = "https://api.elevenlabs.io/v1"
CONFIG_FILE = pathlib.Path(__file__).parent / "agent_config.json"


def _api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY", "").strip()
    if not key:
        sys.exit("ERROR: set ELEVENLABS_API_KEY in your environment.")
    return key


def _headers(api_key: str) -> dict[str, str]:
    return {
        "xi-api-key": api_key,
        "Content-Type": "application/json",
    }


def _load_config() -> dict[str, Any]:
    if not CONFIG_FILE.exists():
        sys.exit(f"ERROR: config file not found at {CONFIG_FILE}")
    return json.loads(CONFIG_FILE.read_text())


def _resolve_env(value_env_key: str, default: str) -> str:
    return os.environ.get(value_env_key, default).strip() or default


def _print_payload(label: str, payload: dict) -> None:
    print(f"\n--- {label} payload --------------------------------")
    print(json.dumps(payload, indent=2))
    print("------------------------------------------------------")


# ── HTTP helpers ───────────────────────────────────────────────────────────


def _post(client: httpx.Client, path: str, body: dict, label: str) -> dict | None:
    r = client.post(f"{API_BASE}{path}", json=body)
    if r.status_code >= 400:
        print(f"  ✗ {label}: HTTP {r.status_code}")
        print(f"    response: {r.text[:400]}")
        _print_payload(label, body)
        return None
    return r.json() if r.text else {}


def _get(client: httpx.Client, path: str) -> dict | list | None:
    r = client.get(f"{API_BASE}{path}")
    if r.status_code >= 400:
        print(f"  (GET {path} -> HTTP {r.status_code}: {r.text[:200]})")
        return None
    return r.json()


def _patch(client: httpx.Client, path: str, body: dict, label: str) -> dict | None:
    r = client.patch(f"{API_BASE}{path}", json=body)
    if r.status_code >= 400:
        print(f"  ✗ {label}: HTTP {r.status_code}")
        print(f"    response: {r.text[:400]}")
        _print_payload(label, body)
        return None
    return r.json() if r.text else {}


# ── Tools ──────────────────────────────────────────────────────────────────


def _build_tool_payload(tool_spec: dict, base_url: str, auth_header: str, auth_secret: str) -> dict:
    """
    Build the ElevenLabs `tool_config` payload for a webhook tool.
    Fields are kept generic — they match the documented `tool_config`
    object for webhook tools.
    """
    return {
        "tool_config": {
            "type": "webhook",
            "name": tool_spec["name"],
            "description": tool_spec["description"],
            "api_schema": {
                "url": f"{base_url.rstrip('/')}{tool_spec['path']}",
                "method": tool_spec.get("method", "POST"),
                "request_body_schema": tool_spec.get("parameters", {}),
                "request_headers": [
                    {
                        "type": "secret",
                        "name": auth_header,
                        "value": auth_secret,
                    }
                ],
            },
        }
    }


def upsert_tools(client: httpx.Client, cfg: dict) -> dict[str, str]:
    """Returns {tool_name: tool_id}."""
    base_url = _resolve_env(cfg["base_url_env"], cfg["base_url_default"])
    auth_header = _resolve_env(cfg["auth_header_env"], cfg["auth_header_default"])
    auth_secret = os.environ.get(cfg["auth_secret_env"], "").strip()
    if not auth_secret:
        print(f"  ! {cfg['auth_secret_env']} is empty — tools will be created without an auth header.")

    print(f"\nBase URL for tool webhooks: {base_url}")
    print(f"Auth header on tools:       {auth_header}\n")

    existing = _get(client, "/convai/tools") or []
    if isinstance(existing, dict):
        existing = existing.get("tools", []) or existing.get("data", [])
    by_name = {
        (t.get("tool_config", {}).get("name") or t.get("name")): t
        for t in existing
        if isinstance(t, dict)
    }

    result: dict[str, str] = {}
    for spec in cfg["tools"]:
        payload = _build_tool_payload(spec, base_url, auth_header, auth_secret)
        existing_entry = by_name.get(spec["name"])

        if existing_entry:
            tool_id = existing_entry.get("id") or existing_entry.get("tool_id")
            print(f"  Updating tool '{spec['name']}' (id={tool_id})")
            data = _patch(client, f"/convai/tools/{tool_id}", payload, f"PATCH tool '{spec['name']}'")
        else:
            print(f"  Creating tool '{spec['name']}'")
            data = _post(client, "/convai/tools", payload, f"POST tool '{spec['name']}'")

        if data:
            tid = data.get("id") or data.get("tool_id") or (existing_entry.get("id") if existing_entry else "")
            if tid:
                result[spec["name"]] = tid
                print(f"    ✓ id={tid}")

    return result


# ── Agent ──────────────────────────────────────────────────────────────────


def upsert_agent(client: httpx.Client, cfg: dict, tool_ids: dict[str, str]) -> str | None:
    agent_spec = cfg["agent"]
    # Attach the tool IDs to the agent's prompt config
    prompt = (
        agent_spec.get("conversation_config", {})
        .get("agent", {})
        .get("prompt", {})
    )
    if tool_ids:
        prompt["tool_ids"] = list(tool_ids.values())

    # See if an agent with this name already exists
    existing = _get(client, "/convai/agents") or {}
    if isinstance(existing, dict):
        agents = existing.get("agents", existing.get("data", []))
    else:
        agents = existing
    by_name = {a.get("name"): a for a in agents if isinstance(a, dict)}

    if agent_spec["name"] in by_name:
        agent_id = by_name[agent_spec["name"]].get("agent_id") or by_name[agent_spec["name"]].get("id")
        print(f"\n  Updating existing agent '{agent_spec['name']}' (id={agent_id})")
        data = _patch(client, f"/convai/agents/{agent_id}", agent_spec, "PATCH agent")
    else:
        print(f"\n  Creating new agent '{agent_spec['name']}'")
        data = _post(client, "/convai/agents/create", agent_spec, "POST agent")

    if not data:
        return None
    return data.get("agent_id") or data.get("id")


# ── Phone number attachment (optional) ─────────────────────────────────────


def attach_phone_numbers(client: httpx.Client, agent_id: str) -> None:
    sask_id = os.environ.get("ELEVENLABS_PHONE_ID_SASKATOON", "").strip()
    regina_id = os.environ.get("ELEVENLABS_PHONE_ID_REGINA", "").strip()
    for label, pid in (("Saskatoon", sask_id), ("Regina", regina_id)):
        if not pid:
            print(f"  (skip {label}: ELEVENLABS_PHONE_ID_{label.upper()} not set)")
            continue
        print(f"  Attaching agent to {label} number (id={pid})")
        _patch(
            client,
            f"/convai/phone-numbers/{pid}",
            {"agent_id": agent_id},
            f"PATCH phone-number {label}",
        )


# ── Entry point ────────────────────────────────────────────────────────────


def main() -> None:
    print("=== Captain Taxi — ElevenLabs Agents Setup ===")
    api_key = _api_key()
    cfg = _load_config()

    with httpx.Client(timeout=30.0, headers=_headers(api_key)) as client:
        tool_ids = upsert_tools(client, cfg)
        if len(tool_ids) != len(cfg["tools"]):
            print(
                f"\n  ! Only {len(tool_ids)}/{len(cfg['tools'])} tools provisioned. "
                "Inspect the errors above and re-run; the script is idempotent."
            )

        agent_id = upsert_agent(client, cfg, tool_ids)
        if not agent_id:
            sys.exit("\nERROR: agent creation failed; see error above.")

        print("\nPhone numbers:")
        attach_phone_numbers(client, agent_id)

    print("\n=== Done ===")
    print(f"  ELEVENLABS_AGENT_ID={agent_id}")
    print("  Copy the agent ID into customer/.env, then call the Saskatoon or")
    print("  Regina number to test (or run: python scripts/test_elevenlabs_bot.py).")


if __name__ == "__main__":
    main()
