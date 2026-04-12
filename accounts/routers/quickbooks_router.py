"""QuickBooks OAuth routes."""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from database import get_db
import services.quickbooks as qb_service

router = APIRouter(prefix="/qb", tags=["QuickBooks"])


@router.get("/connect")
def qb_connect():
    """Redirect owner to QuickBooks consent screen."""
    url = qb_service.get_authorization_url()
    return RedirectResponse(url)


@router.get("/callback")
def qb_callback(code: str, state: str = "", realmId: str = "", db: Session = Depends(get_db)):
    """Handle QuickBooks OAuth callback."""
    if not code or not realmId:
        raise HTTPException(400, "Missing code or realmId from QuickBooks")
    try:
        token = qb_service.exchange_code_for_tokens(db, code=code, realm_id=realmId)
        return {
            "status": "connected",
            "realm_id": token.realm_id,
            "message": "QuickBooks connected successfully. You can close this window.",
        }
    except Exception as exc:
        raise HTTPException(500, f"QuickBooks auth failed: {exc}")


@router.get("/status")
def qb_status(db: Session = Depends(get_db)):
    """Check if QB is connected."""
    from config import settings
    from models.qb_token import QBToken
    token = db.query(QBToken).filter_by(realm_id=settings.qb_realm_id).first()
    if not token:
        return {"connected": False, "message": "Visit /accounts/qb/connect to authorize QuickBooks."}
    return {
        "connected": True,
        "realm_id": token.realm_id,
        "access_expires": token.access_token_expires_at,
        "refresh_expires": token.refresh_token_expires_at,
    }
