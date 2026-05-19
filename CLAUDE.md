# Captain Taxi — Claude Instructions

## Read This First

**At the start of every session, read `PROJECT_STATE.md` in full before doing anything else.**
It is the authoritative record of what has been built, what is pending, and what decisions were made.

## At the End of Every Session

**Update `PROJECT_STATE.md` before closing.** Record:
- What was completed this session (move items from "Next Tasks" to the relevant service's ✅ section)
- Any new gaps or tasks discovered
- Any decisions made (architecture, credentials, logic changes)
- Update the `Last updated` date at the top

This keeps the project state accurate for the next session — whether that's you or another Claude instance.

## Project Summary

Captain Taxi is a multi-agent AI system that runs a taxi company in Saskatoon & Regina, SK with minimum human input.

- **Owner:** WhatsApp +13068811542
- **Amara (co-decision-maker):** +13068500760
- **Commission split:** 70% driver / 30% company

## Services at a Glance

| Service | Port | Stack |
|---|---|---|
| orchestrator | 8000 | FastAPI + Claude |
| dispatch | 8001 | FastAPI |
| customer | 8002 | FastAPI + Claude + ElevenLabs + Twilio |
| drivers | 8003 | FastAPI + Claude |
| accounts | 8004 | FastAPI |
| compliance | 8005 | FastAPI |
| admin | 8006 | FastAPI + Claude |
| dashboard | 3000 | React + Vite + Tailwind |

**Infrastructure:** PostgreSQL 16, Redis 7, Nginx, Docker Compose.

## Escalation Rules (Owner contacted ONLY for)
1. Driver termination / firing
2. Expenses or payments > $500 (non-routine)
3. Legal threats, lawsuits, police, criminal matters
4. New contracts or partnership agreements
5. Anything that could seriously harm the company

## Key Rules for Claude

- **Voice stack is ElevenLabs Conversational AI + Twilio. NOT Vapi.** Do not suggest, scaffold, or reintroduce Vapi. Phone calls go: Twilio number → ElevenLabs Conversational AI (handles STT, LLM, TTS, turn-taking) → webhook to `customer/routers/elevenlabs.py` for tool execution (`create_booking` etc.) → dispatch service.
- **Do not invent credentials.** All API keys (Twilio, ElevenLabs, QuickBooks, iCabbi) must come from the owner's `.env` file.
- **Do not over-engineer.** Build what is needed now, not hypothetical future features.
- **Keep services decoupled.** Services communicate via HTTP or Redis pub/sub — never direct DB cross-service queries.
- **Security first.** No command injection, no SQL injection, validate at system boundaries only.
- **Update `PROJECT_STATE.md` every session** — this is non-negotiable.
