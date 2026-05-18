"""
Vapi assistant provisioning script.

Run once to create (or update) the Captain Taxi assistant in Vapi
and attach it to both phone numbers.

Usage:
    python -m captain_taxi.customer.vapi.setup
"""

import asyncio
import json
import pathlib
import httpx
import sys
from config import get_settings

settings = get_settings()

VAPI_BASE   = "https://api.vapi.ai"
_API_KEY    = settings.vapi_api_key or settings.vapi_private_key
HEADERS     = {
    "Authorization": f"Bearer {_API_KEY}",
    "Content-Type": "application/json",
}
CONFIG_FILE = pathlib.Path(__file__).parent / "assistant_config.json"


async def upsert_assistant(client: httpx.AsyncClient) -> str:
    """Create or update the assistant. Returns the assistant ID."""
    config = json.loads(CONFIG_FILE.read_text())

    # Inject real webhook secret if configured
    if settings.vapi_webhook_secret:
        config["serverUrlSecret"] = settings.vapi_webhook_secret
        for tool in config.get("model", {}).get("tools", []):
            if "server" in tool:
                tool["server"]["secret"] = settings.vapi_webhook_secret

    # Check for existing assistant
    resp = await client.get(f"{VAPI_BASE}/assistant", headers=HEADERS)
    resp.raise_for_status()
    existing = resp.json()

    for asst in existing:
        if asst.get("name") == config["name"]:
            asst_id = asst["id"]
            print(f"  Updating existing assistant {asst_id}")
            r = await client.patch(
                f"{VAPI_BASE}/assistant/{asst_id}",
                json=config,
                headers=HEADERS,
            )
            r.raise_for_status()
            return asst_id

    print("  Creating new assistant")
    r = await client.post(f"{VAPI_BASE}/assistant", json=config, headers=HEADERS)
    r.raise_for_status()
    return r.json()["id"]


async def attach_phone_number(client: httpx.AsyncClient, phone_number_id: str, assistant_id: str) -> None:
    if not phone_number_id:
        return
    print(f"  Attaching assistant to phone number {phone_number_id}")
    r = await client.patch(
        f"{VAPI_BASE}/phone-number/{phone_number_id}",
        json={"assistantId": assistant_id},
        headers=HEADERS,
    )
    r.raise_for_status()


async def main() -> None:
    print("=== Captain Taxi — Vapi Assistant Setup ===")
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("Upserting assistant…")
        asst_id = await upsert_assistant(client)
        print(f"  Assistant ID: {asst_id}")

        print("Attaching to Saskatoon number…")
        await attach_phone_number(client, settings.vapi_phone_number_id_saskatoon, asst_id)

        print("Attaching to Regina number…")
        await attach_phone_number(client, settings.vapi_phone_number_id_regina, asst_id)

    print("Done! The voice agent is live on both numbers.")
    print(f"  Assistant ID: {asst_id}")
    print("  Test by calling 306-242-0000 or 306-775-2222.")


if __name__ == "__main__":
    asyncio.run(main())
