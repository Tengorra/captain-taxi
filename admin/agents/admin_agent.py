"""
Admin Agent — Claude-powered brain for internal admin tasks.
Handles HR document drafting, digest generation, and smart query responses.
"""
import os
import json
from datetime import datetime
from anthropic import Anthropic
from dotenv import load_dotenv

load_dotenv()

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-sonnet-4-6"

SYSTEM_PROMPT = """You are the Admin Agent for Captain Taxi, a taxi company operating in
Saskatoon and Regina, Saskatchewan, Canada. You assist the owner and his wife Amara with:

1. Drafting HR documents (offer letters, warning letters, policy updates)
2. Answering questions about the business in a clear, concise way
3. Formatting escalation summaries for owner review
4. Generating daily digest messages

Company context:
- Fleet: 31-60 drivers across both cities
- Commission structure: drivers keep 70%, company takes 30%
- Key contacts: Owner (decision maker) and Amara (wife, co-decision maker)
- Dispatch platform: iCabbi/Autocab

Always be professional, clear, and concise. For HR documents, use formal Canadian English.
When in doubt, escalate to the owner rather than making assumptions."""


def draft_hr_document(doc_type: str, context: dict) -> str:
    """
    Draft an HR document using Claude.
    doc_type: 'offer_letter' | 'warning_letter' | 'policy_update' | 'termination'
    context: dict with relevant details (driver_name, reason, etc.)
    """
    prompts = {
        "offer_letter": f"""Draft a professional driver offer letter for Captain Taxi.
Details: {json.dumps(context, indent=2)}
Include: position title, start date, commission rate (70/30 split), city,
vehicle requirements, and standard employment terms for Saskatchewan.
Format as a proper business letter.""",

        "warning_letter": f"""Draft a formal warning letter for Captain Taxi.
Details: {json.dumps(context, indent=2)}
Include: specific incident/behaviour, expectations going forward,
consequences if behaviour continues, signature lines.
Tone: firm but professional. Follow Saskatchewan employment standards.""",

        "policy_update": f"""Draft a policy update notice for Captain Taxi drivers.
Details: {json.dumps(context, indent=2)}
Format as a clear memo. Explain the change, effective date, and what drivers need to do.
Keep it concise — drivers are busy.""",

        "termination": f"""Draft a termination letter for Captain Taxi.
Details: {json.dumps(context, indent=2)}
Include: effective date, reason (if appropriate), final pay arrangements,
return of company materials. Follow Saskatchewan Employment Standards Act.""",
    }

    prompt = prompts.get(doc_type, f"Draft a professional {doc_type} document for: {json.dumps(context)}")

    response = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def format_escalation_for_owner(escalation: dict) -> str:
    """Format an escalation from any agent into a clear WhatsApp message for the owner."""
    prompt = f"""Format this escalation as a WhatsApp message for the taxi company owner.
Be very concise — max 5 lines. Start with the urgency level.
Include the exact question needing a YES/NO decision.
End with: Reply APPROVE [id] or DENY [id]

Escalation: {json.dumps(escalation, indent=2)}"""

    response = client.messages.create(
        model=MODEL,
        max_tokens=500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def answer_owner_query(query: str, context: dict) -> str:
    """
    Answer a natural language query from the owner via WhatsApp.
    context: live data dict from Redis/DB (drivers online, revenue, etc.)
    """
    prompt = f"""The owner sent this WhatsApp message: "{query}"

Current business data:
{json.dumps(context, indent=2)}

Answer in 1-3 short lines suitable for WhatsApp. Be direct and helpful.
If the query requires an action (like suspending a driver), confirm the action
and ask for explicit confirmation before proceeding."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=300,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text


def generate_daily_digest(data: dict) -> str:
    """
    Generate the morning WhatsApp digest message for the owner.
    data: yesterday's stats from DB
    """
    prompt = f"""Generate a morning digest WhatsApp message for the Captain Taxi owner.
Date: {datetime.now().strftime('%A, %B %d, %Y')}
Yesterday's data: {json.dumps(data, indent=2)}

Format (use emojis, keep it scannable):
- Good morning greeting
- Yesterday's key numbers (trips, revenue by city)
- Any driver issues
- Compliance alerts (if any)
- Active escalations waiting (if any)
- One sentence about today's outlook

Max 15 lines. This is a WhatsApp message so use line breaks well."""

    response = client.messages.create(
        model=MODEL,
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}]
    )
    return response.content[0].text
