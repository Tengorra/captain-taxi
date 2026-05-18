import uuid
from datetime import datetime, date
from typing import Optional, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from ...db.database import get_db
from ...db.models import Driver, Vehicle, Trip, DriverSite


SITE_REGISTRY = {
    "CTS": "Captain Taxi Saskatoon",
    "CTR": "Captain Taxi Regina",
}


class SiteAssignment(BaseModel):
    site_code: str
    assigned: bool = True
    is_primary: bool = False

router = APIRouter(prefix="/drivers", tags=["drivers"])

# Status values used in actual DB (from drivers agent)
ONLINE_STATUSES = {"active", "on_trip", "available"}
SUSPENDED_STATUS = "suspended"


class DriverCreate(BaseModel):
    """
    Accepts the full iCabbi field set. Every field is optional — a blank
    iCabbi row (e.g. an `_copy` placeholder) is allowed through. Mandatory-
    field enforcement for manual entry happens client-side and will be
    configurable via Settings in a future change.
    """
    # Identity
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    aka: Optional[str] = None
    gender: Optional[str] = None             # M / F / other
    sex: Optional[str] = None                # legacy alias from old client form
    address: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None              # iCabbi Phone column
    mobile: Optional[str] = None             # iCabbi MOBILE column
    mobile_phone: Optional[str] = None       # legacy alias
    other_phone: Optional[str] = None        # legacy alias
    city: Optional[str] = None

    # Status
    status: Optional[str] = "pending"
    is_active_flag: Optional[bool] = None    # iCabbi ACTIVE
    is_deleted: Optional[bool] = None        # iCabbi DELETED
    driver_type: Optional[str] = "regular"

    # iCabbi linkage
    icabbi_driver_id: Optional[str] = None   # iCabbi DRIVER id
    icabbi_ref: Optional[str] = None         # iCabbi REF (used to de-dupe imports)
    vehicle_ref: Optional[str] = None        # iCabbi Vehicle column
    start_date: Optional[str] = None         # ISO date string

    # Licensing
    licence_number: Optional[str] = None
    licence_expiry: Optional[str] = None
    badge_number: Optional[str] = None       # BADGE/PSV
    badge_expiry: Optional[str] = None       # PSV EXPIRY
    badge_type: Optional[str] = None         # HACKNEY / PRIVATE HIRE
    school_badge_expiry: Optional[str] = None
    ni_number: Optional[str] = None
    tax_number: Optional[str] = None         # legacy alias for ni_number

    # Vehicle (kept for backward compat; populates vehicles table when present)
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_year: Optional[int] = None
    vehicle_plate: Optional[str] = None
    vehicle_color: Optional[str] = None

    # Device / app
    imei_udid: Optional[str] = None
    app_version: Optional[str] = None
    legacy_version: Optional[str] = None
    installed_legacy_version: Optional[str] = None
    phone_os: Optional[str] = None
    phone_os_version: Optional[str] = None
    phone_manufacturer: Optional[str] = None
    phone_model: Optional[str] = None
    phone_locked: Optional[bool] = None
    profile_photo: Optional[str] = None

    # Activity
    last_updated_at: Optional[str] = None
    last_active_at: Optional[str] = None

    # Payments
    commission_rate: Optional[float] = 0.30
    payment_type: Optional[str] = None
    payment_period: Optional[int] = None
    payment_terms: Optional[int] = None
    last_payment_at: Optional[str] = None
    output_preference: Optional[str] = None
    frequency: Optional[str] = None
    frequency_day: Optional[int] = None
    si_id: Optional[str] = None
    payment_on: Optional[str] = None         # legacy alias
    bank_name: Optional[str] = None
    bank_account_number: Optional[str] = None
    sort_code: Optional[str] = None

    # Auth
    login_username: Optional[str] = None
    login_password: Optional[str] = None  # hashed on save

    # Personal extras
    ethnicity: Optional[str] = None
    transporter: Optional[bool] = None
    payment_card_last4: Optional[str] = None
    payment_card_expiry: Optional[str] = None  # YYYY-MM or YYYY-MM-DD

    # Custom fields
    pvg_disclosure: Optional[str] = None
    police_record: Optional[str] = None
    police_record_2: Optional[str] = None

    # Attributes
    attr_pets: Optional[bool] = None
    attr_uniformed: Optional[bool] = None
    attr_topman: Optional[bool] = None
    attr_accept_discount: Optional[bool] = None
    attr_accept_account: Optional[bool] = None
    attr_accept_fixed_fares: Optional[bool] = None
    attr_accept_cash_work: Optional[bool] = None

    # Device extras
    phone_assist: Optional[bool] = None

    # Invoicing / Shifts
    invoice_footer: Optional[str] = None
    shift_reporting: Optional[bool] = None

    # Payments / VAT
    payment_on_day: Optional[str] = None
    distribution: Optional[str] = None
    apply_vat: Optional[bool] = None
    vat_rate: Optional[float] = None
    balance: Optional[float] = None
    exclude_booking_fee: Optional[bool] = None
    auto_post: Optional[str] = None
    bank_payment_ref: Optional[str] = None
    use_sepa: Optional[bool] = None
    bank_account_name: Optional[str] = None

    # Breathalyser
    breathalyser_enabled: Optional[bool] = None

    # Fatigue
    fatigue_max_work_hours: Optional[int] = None
    fatigue_min_rest_hours: Optional[int] = None
    fatigue_exceed_job_pct: Optional[int] = None
    fatigue_send_alert_pct: Optional[int] = None

    # Sites (CTS, CTR)
    sites: Optional[list[SiteAssignment]] = None

    # Catch-all for the deep iCabbi app-config flags
    icabbi_config: Optional[dict[str, Any]] = None

    notes: Optional[str] = None


class DriverUpdate(BaseModel):
    # Mirror DriverCreate for editability — every field optional, only the
    # ones the client sends are touched.
    # Identity
    name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    aka: Optional[str] = None
    gender: Optional[str] = None
    sex: Optional[str] = None
    ethnicity: Optional[str] = None
    address: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    mobile: Optional[str] = None
    mobile_phone: Optional[str] = None
    other_phone: Optional[str] = None
    city: Optional[str] = None
    status: Optional[str] = None
    is_active_flag: Optional[bool] = None
    is_deleted: Optional[bool] = None
    driver_type: Optional[str] = None
    transporter: Optional[bool] = None
    # Auth
    login_username: Optional[str] = None
    login_password: Optional[str] = None
    # Payment card
    payment_card_last4: Optional[str] = None
    payment_card_expiry: Optional[str] = None
    # Licensing
    licence_number: Optional[str] = None
    licence_expiry: Optional[str] = None
    badge_number: Optional[str] = None
    badge_expiry: Optional[str] = None
    badge_type: Optional[str] = None
    school_badge_expiry: Optional[str] = None
    ni_number: Optional[str] = None
    tax_number: Optional[str] = None
    pvg_disclosure: Optional[str] = None
    # Vehicle
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_plate: Optional[str] = None
    vehicle_color: Optional[str] = None
    vehicle_year: Optional[int] = None
    vehicle_ref: Optional[str] = None
    # Attributes
    attr_pets: Optional[bool] = None
    attr_uniformed: Optional[bool] = None
    attr_topman: Optional[bool] = None
    attr_accept_discount: Optional[bool] = None
    attr_accept_account: Optional[bool] = None
    attr_accept_fixed_fares: Optional[bool] = None
    attr_accept_cash_work: Optional[bool] = None
    # Custom fields
    police_record: Optional[str] = None
    police_record_2: Optional[str] = None
    breathalyser_enabled: Optional[bool] = None
    # Device
    phone_assist: Optional[bool] = None
    phone_locked: Optional[bool] = None
    imei_udid: Optional[str] = None
    # Invoicing / shifts
    frequency: Optional[str] = None
    frequency_day: Optional[int] = None
    invoice_footer: Optional[str] = None
    shift_reporting: Optional[bool] = None
    payment_period: Optional[int] = None
    payment_terms: Optional[int] = None
    output_preference: Optional[str] = None
    si_id: Optional[str] = None
    # Payments / VAT
    commission_rate: Optional[float] = None
    payment_type: Optional[str] = None
    payment_on_day: Optional[str] = None
    distribution: Optional[str] = None
    apply_vat: Optional[bool] = None
    vat_rate: Optional[float] = None
    balance: Optional[float] = None
    exclude_booking_fee: Optional[bool] = None
    auto_post: Optional[str] = None
    # Bank
    bank_payment_ref: Optional[str] = None
    use_sepa: Optional[bool] = None
    bank_name: Optional[str] = None
    bank_account_name: Optional[str] = None
    sort_code: Optional[str] = None
    bank_account_number: Optional[str] = None
    # Fatigue
    fatigue_max_work_hours: Optional[int] = None
    fatigue_min_rest_hours: Optional[int] = None
    fatigue_exceed_job_pct: Optional[int] = None
    fatigue_send_alert_pct: Optional[int] = None
    # Sites — when supplied, completely replaces existing assignments
    sites: Optional[list[SiteAssignment]] = None
    # Misc
    performance_score: Optional[float] = None
    notes: Optional[str] = None


class MessageBody(BaseModel):
    message: str


STATUS_MAP = {
    "pending":   "onboarding",
    "active":    "active",
    "offline":   "inactive",
    "inactive":  "inactive",
    "suspended": "suspended",
    "on_trip":   "active",
}


def _parse_date(val: Optional[str]) -> Optional[date]:
    """Parse YYYY-MM-DD into a date. Returns None for empty or unparseable values.
    Also accepts YYYY-MM (treats day as 01) — payment-card expiry only stores
    month + year in iCabbi."""
    if not val:
        return None
    try:
        return datetime.strptime(val[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        pass
    try:
        return datetime.strptime(val[:7] + "-01", "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _hash_password(raw: Optional[str]) -> Optional[str]:
    """Cheap one-way hash so the login_password column never stores plaintext.
    We aren't using bcrypt here to avoid adding a runtime dep — the field is
    a UI parity-with-iCabbi feature for now, not a production auth credential."""
    if not raw:
        return None
    import hashlib
    return "sha256$" + hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _parse_datetime(val: Optional[str]) -> Optional[datetime]:
    """Parse YYYY-MM-DD or full ISO datetime. Returns None for empty/unparseable."""
    if not val:
        return None
    try:
        # Try full ISO first
        return datetime.fromisoformat(val.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        pass
    try:
        return datetime.strptime(val[:10], "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


@router.post("/")
def create_driver(body: DriverCreate, db: Session = Depends(get_db)):
    # Skip-duplicate behavior: if a driver with the same iCabbi REF already
    # exists, return 409 so the dashboard can count it as a dupe and move on.
    if body.icabbi_ref:
        existing = db.query(Driver).filter(Driver.icabbi_ref == body.icabbi_ref).first()
        if existing:
            raise HTTPException(409, f"Driver with iCabbi REF {body.icabbi_ref} already exists")

    # Build display name from first+last when not provided. Allow blank — the
    # user wants placeholder/_copy iCabbi rows to import cleanly.
    display_name = (body.name or "").strip() or \
                   f"{(body.first_name or '').strip()} {(body.last_name or '').strip()}".strip() or \
                   None

    # gender/sex aliases — accept either
    gender = (body.gender or body.sex or None)
    if gender:
        gender = gender[:10]
    # mobile aliases
    mobile = body.mobile or body.mobile_phone or None
    # ni_number alias
    ni_number = body.ni_number or body.tax_number

    driver = Driver(
        id=str(uuid.uuid4()),
        # Identity
        name=display_name,
        first_name=body.first_name,
        last_name=body.last_name,
        aka=body.aka,
        gender=gender,
        address=body.address,
        email=body.email,
        phone=body.phone,
        mobile=mobile,
        city=body.city,
        # Status
        status=STATUS_MAP.get(body.status or "pending", "onboarding"),
        is_active_flag=body.is_active_flag if body.is_active_flag is not None else False,
        is_deleted=body.is_deleted if body.is_deleted is not None else False,
        driver_type=body.driver_type or "regular",
        # iCabbi linkage
        icabbi_driver_id=body.icabbi_driver_id,
        icabbi_ref=body.icabbi_ref,
        vehicle_ref=body.vehicle_ref,
        start_date=_parse_datetime(body.start_date),
        # Licensing
        license_number=body.licence_number,
        license_expiry=_parse_date(body.licence_expiry),
        taxi_license_number=body.badge_number,
        taxi_license_expiry=_parse_date(body.badge_expiry),
        badge_type=body.badge_type,
        school_badge_expiry=_parse_date(body.school_badge_expiry),
        ni_number=ni_number,
        # Device / app
        imei_udid=body.imei_udid,
        app_version=body.app_version,
        legacy_version=body.legacy_version,
        installed_legacy_version=body.installed_legacy_version,
        phone_os=body.phone_os,
        phone_os_version=body.phone_os_version,
        phone_manufacturer=body.phone_manufacturer,
        phone_model=body.phone_model,
        phone_locked=body.phone_locked if body.phone_locked is not None else False,
        profile_photo=body.profile_photo,
        # Activity
        last_updated_at=_parse_datetime(body.last_updated_at),
        last_active_at=_parse_datetime(body.last_active_at),
        # Payments
        commission_rate=body.commission_rate if body.commission_rate is not None else 0.30,
        payment_type=body.payment_type,
        payment_period=body.payment_period,
        payment_terms=body.payment_terms,
        last_payment_at=_parse_datetime(body.last_payment_at),
        output_preference=body.output_preference,
        frequency=body.frequency,
        frequency_day=body.frequency_day,
        si_id=body.si_id,
        # Catch-all
        icabbi_config=body.icabbi_config,
        notes=body.notes,
        # Auth
        login_username=body.login_username,
        login_password_hash=_hash_password(body.login_password),
        # Personal extras
        ethnicity=body.ethnicity,
        transporter=bool(body.transporter) if body.transporter is not None else False,
        payment_card_last4=body.payment_card_last4,
        payment_card_expiry=_parse_date(body.payment_card_expiry),
        # Custom fields
        pvg_disclosure=body.pvg_disclosure,
        police_record=body.police_record,
        police_record_2=body.police_record_2,
        # Attributes
        attr_pets=bool(body.attr_pets) if body.attr_pets is not None else False,
        attr_uniformed=bool(body.attr_uniformed) if body.attr_uniformed is not None else False,
        attr_topman=bool(body.attr_topman) if body.attr_topman is not None else False,
        attr_accept_discount=bool(body.attr_accept_discount) if body.attr_accept_discount is not None else True,
        attr_accept_account=bool(body.attr_accept_account) if body.attr_accept_account is not None else True,
        attr_accept_fixed_fares=bool(body.attr_accept_fixed_fares) if body.attr_accept_fixed_fares is not None else True,
        attr_accept_cash_work=bool(body.attr_accept_cash_work) if body.attr_accept_cash_work is not None else True,
        phone_assist=bool(body.phone_assist) if body.phone_assist is not None else False,
        # Invoicing / shifts
        invoice_footer=body.invoice_footer,
        shift_reporting=bool(body.shift_reporting) if body.shift_reporting is not None else False,
        # Payments / VAT
        payment_on_day=body.payment_on_day or body.payment_on,
        distribution=body.distribution,
        apply_vat=bool(body.apply_vat) if body.apply_vat is not None else False,
        vat_rate=body.vat_rate,
        balance=body.balance,
        exclude_booking_fee=bool(body.exclude_booking_fee) if body.exclude_booking_fee is not None else False,
        auto_post=body.auto_post,
        bank_payment_ref=body.bank_payment_ref,
        use_sepa=bool(body.use_sepa) if body.use_sepa is not None else False,
        bank_name=body.bank_name,
        bank_account_name=body.bank_account_name,
        sort_code=body.sort_code,
        bank_account_number=body.bank_account_number,
        # Breathalyser
        breathalyser_enabled=bool(body.breathalyser_enabled) if body.breathalyser_enabled is not None else False,
        # Fatigue
        fatigue_max_work_hours=body.fatigue_max_work_hours,
        fatigue_min_rest_hours=body.fatigue_min_rest_hours,
        fatigue_exceed_job_pct=body.fatigue_exceed_job_pct,
        fatigue_send_alert_pct=body.fatigue_send_alert_pct,
    )
    db.add(driver)
    db.flush()  # get ID before creating vehicle / site rows

    # Site assignments (CTS / CTR / etc.) — only one row per (driver, site).
    if body.sites:
        primary_seen = False
        for s in body.sites:
            code = s.site_code.upper().strip()
            name = SITE_REGISTRY.get(code, code)
            is_primary = bool(s.is_primary) and not primary_seen
            if is_primary:
                primary_seen = True
            db.add(DriverSite(
                id=str(uuid.uuid4()),
                driver_id=driver.id,
                site_code=code,
                site_name=name,
                assigned=bool(s.assigned),
                is_primary=is_primary,
            ))

    if body.vehicle_plate:
        # vehicle_make/model can come in as separate fields OR as "Make Model"
        # in vehicle_model. Prefer explicit make when provided.
        make = (body.vehicle_make or "").strip()
        model = (body.vehicle_model or "").strip()
        if not make and model:
            parts = model.split(" ", 1)
            make = parts[0] or "Unknown"
            model = parts[1] if len(parts) > 1 else ""
        if not make:
            make = "Unknown"
        vehicle = Vehicle(
            id=str(uuid.uuid4()),
            plate=body.vehicle_plate.upper().strip(),
            make=make,
            model=model,
            year=body.vehicle_year or datetime.utcnow().year,
            color=body.vehicle_color,
            driver_id=driver.id,
            city=body.city or "saskatoon",
        )
        db.add(vehicle)

    db.commit()
    db.refresh(driver)
    return _driver_summary(driver, db)


@router.get("/")
def list_drivers(
    city: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db)
):
    q = db.query(Driver)
    if city:
        q = q.filter(Driver.city == city)
    if status:
        q = q.filter(Driver.status == status)
    if search:
        q = q.filter(Driver.name.ilike(f"%{search}%"))
    drivers = q.order_by(Driver.name).all()
    return [_driver_summary(d, db) for d in drivers]


@router.get("/{driver_id}")
def get_driver(driver_id: str, db: Session = Depends(get_db)):
    driver = db.query(Driver).filter_by(id=driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    return _driver_detail(driver, db)


@router.patch("/{driver_id}")
def update_driver(driver_id: str, body: DriverUpdate, db: Session = Depends(get_db)):
    driver = db.query(Driver).filter_by(id=driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")

    data = body.model_dump(exclude_unset=True)

    # Pull aliases / fields needing transforms out before the generic loop so
    # they don't double-assign.
    if "login_password" in data:
        pw = data.pop("login_password")
        driver.login_password_hash = _hash_password(pw)
    if "mobile_phone" in data and "mobile" not in data:
        data["mobile"] = data.pop("mobile_phone")
    else:
        data.pop("mobile_phone", None)
    if "sex" in data and "gender" not in data:
        data["gender"] = data.pop("sex")
    else:
        data.pop("sex", None)
    if "tax_number" in data and "ni_number" not in data:
        data["ni_number"] = data.pop("tax_number")
    else:
        data.pop("tax_number", None)

    # Column-name aliases — the iCabbi UI calls these `badge_*` / `licence_*`
    # but our DB stores them under the legacy taxi/license names.
    if "licence_number" in data:
        driver.license_number = data.pop("licence_number")
    if "licence_expiry" in data:
        driver.license_expiry = _parse_date(data.pop("licence_expiry"))
    if "badge_number" in data:
        driver.taxi_license_number = data.pop("badge_number")
    if "badge_expiry" in data:
        driver.taxi_license_expiry = _parse_date(data.pop("badge_expiry"))
    if "school_badge_expiry" in data:
        driver.school_badge_expiry = _parse_date(data.pop("school_badge_expiry"))
    if "payment_card_expiry" in data:
        driver.payment_card_expiry = _parse_date(data.pop("payment_card_expiry"))

    # Site replacement — atomic: drop everything, re-create from the new list.
    if "sites" in data:
        sites = data.pop("sites") or []
        db.query(DriverSite).filter(DriverSite.driver_id == driver.id).delete()
        primary_seen = False
        for s in sites:
            code = (s.get("site_code") or "").upper().strip()
            if not code:
                continue
            is_primary = bool(s.get("is_primary")) and not primary_seen
            if is_primary:
                primary_seen = True
            db.add(DriverSite(
                id=str(uuid.uuid4()),
                driver_id=driver.id,
                site_code=code,
                site_name=SITE_REGISTRY.get(code, code),
                assigned=bool(s.get("assigned", True)),
                is_primary=is_primary,
            ))

    # Vehicle quick-edit — patch the active vehicle row if one exists.
    veh_keys = {"vehicle_make", "vehicle_model", "vehicle_plate",
                "vehicle_color", "vehicle_year"}
    veh_data = {k: data.pop(k) for k in list(data) if k in veh_keys}
    if veh_data:
        vehicle = _get_vehicle(driver.id, db)
        if vehicle:
            if "vehicle_plate" in veh_data and veh_data["vehicle_plate"]:
                vehicle.plate = veh_data["vehicle_plate"].upper().strip()
            if "vehicle_make" in veh_data:
                vehicle.make = veh_data["vehicle_make"]
            if "vehicle_model" in veh_data:
                vehicle.model = veh_data["vehicle_model"]
            if "vehicle_color" in veh_data:
                vehicle.color = veh_data["vehicle_color"]
            if "vehicle_year" in veh_data and veh_data["vehicle_year"]:
                vehicle.year = veh_data["vehicle_year"]

    # status alias (UI sends "pending" / "offline" — translate to internal)
    if "status" in data and data["status"] in STATUS_MAP:
        data["status"] = STATUS_MAP[data["status"]]

    # Remaining fields are 1:1 with column names.
    for field, val in data.items():
        if hasattr(driver, field):
            setattr(driver, field, val)

    driver.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(driver)
    return {"ok": True, "driver": _driver_detail(driver, db)}


@router.post("/{driver_id}/suspend")
def suspend_driver(driver_id: str, db: Session = Depends(get_db)):
    driver = db.query(Driver).filter_by(id=driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    driver.status = SUSPENDED_STATUS
    driver.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "message": f"{driver.name} suspended"}


@router.post("/{driver_id}/activate")
def activate_driver(driver_id: str, db: Session = Depends(get_db)):
    driver = db.query(Driver).filter_by(id=driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    driver.status = "offline"
    driver.updated_at = datetime.utcnow()
    db.commit()
    return {"ok": True, "message": f"{driver.name} activated"}


@router.post("/{driver_id}/message")
def send_message(driver_id: str, body: MessageBody, db: Session = Depends(get_db)):
    driver = db.query(Driver).filter_by(id=driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    if not driver.phone:
        raise HTTPException(400, "Driver has no phone number")
    from ...services.twilio_service import send_sms
    sid = send_sms(driver.phone, body.message)
    return {"ok": True, "sid": sid}


@router.get("/{driver_id}/trips")
def get_driver_trips(driver_id: str, limit: int = 50, db: Session = Depends(get_db)):
    trips = (
        db.query(Trip)
        .filter(Trip.driver_id == driver_id)
        .order_by(Trip.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": t.id,
            "city": t.city,
            "status": t.status,
            "pickup": t.pickup_address,
            "dropoff": t.dropoff_address,
            "fare": t.fare or 0,
            "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        }
        for t in trips
    ]


@router.get("/{driver_id}/documents")
def get_driver_documents(driver_id: str, db: Session = Depends(get_db)):
    from ...db.models import Document
    docs = db.query(Document).filter(
        Document.entity_id == driver_id,
        Document.entity_type == "driver"
    ).all()
    return [
        {
            "id": d.id,
            "type": d.doc_type,
            "status": d.status,
            "expiry_date": d.expiry_date.isoformat() if d.expiry_date else None,
            "uploaded_at": d.uploaded_at.isoformat() if d.uploaded_at else None,
        }
        for d in docs
    ]


def _get_vehicle(driver_id: str, db: Session) -> Optional[Vehicle]:
    return db.query(Vehicle).filter(
        Vehicle.driver_id == driver_id,
        Vehicle.is_active == True
    ).first()


def _driver_summary(d: Driver, db: Session) -> dict:
    vehicle = _get_vehicle(d.id, db)
    display_name = d.name or f"{d.first_name or ''} {d.last_name or ''}".strip() or "—"
    return {
        "id": d.id,
        "name": display_name,
        "first_name": d.first_name,
        "last_name": d.last_name,
        "phone": d.phone,
        "mobile": d.mobile,
        "email": d.email,
        "city": d.city,
        "status": d.status,
        "is_active_flag": bool(d.is_active_flag),
        "is_deleted": bool(d.is_deleted),
        "performance_score": d.performance_score if d.performance_score is not None else 100.0,
        "commission_rate": d.commission_rate if d.commission_rate is not None else 0.30,
        "vehicle_plate": vehicle.plate if vehicle else None,
        "vehicle_model": f"{vehicle.make} {vehicle.model}".strip() if vehicle else None,
        "vehicle_ref": d.vehicle_ref,
        # iCabbi linkage / key columns shown in the search table
        "icabbi_ref": d.icabbi_ref,
        "icabbi_driver_id": d.icabbi_driver_id,
        "badge_number": d.taxi_license_number,
        "badge_expiry": d.taxi_license_expiry.isoformat() if d.taxi_license_expiry else None,
        "badge_type": d.badge_type,
        "licence_number": d.license_number,
        "licence_expiry": d.license_expiry.isoformat() if d.license_expiry else None,
        "last_active_at": d.last_active_at.isoformat() if d.last_active_at else None,
        "last_updated_at": d.last_updated_at.isoformat() if d.last_updated_at else None,
        "start_date": d.start_date.isoformat() if d.start_date else None,
        "address": d.address,
        "gender": d.gender,
        "phone_os": d.phone_os,
        "phone_model": d.phone_model,
        # Attributes (shown as YES/NO chips in the iCabbi-style table)
        "attr_pets": bool(d.attr_pets),
        "attr_uniformed": bool(d.attr_uniformed),
        "attr_topman": bool(d.attr_topman),
        "attr_accept_discount": bool(d.attr_accept_discount),
        "attr_accept_account": bool(d.attr_accept_account),
        "attr_accept_fixed_fares": bool(d.attr_accept_fixed_fares),
        "attr_accept_cash_work": bool(d.attr_accept_cash_work),
        "transporter": bool(d.transporter),
    }


def _driver_detail(d: Driver, db: Session) -> dict:
    summary = _driver_summary(d, db)
    summary["email"] = d.email
    summary["notes"] = d.notes
    summary["created_at"] = d.created_at.isoformat() if d.created_at else None

    # Auth (never return the hash itself — just whether one's set)
    summary["login_username"] = d.login_username
    summary["has_login_password"] = bool(d.login_password_hash)

    # Personal extras
    summary["ethnicity"] = d.ethnicity
    summary["payment_card_last4"] = d.payment_card_last4
    summary["payment_card_expiry"] = d.payment_card_expiry.isoformat() if d.payment_card_expiry else None

    # Custom fields
    summary["pvg_disclosure"] = d.pvg_disclosure
    summary["police_record"] = d.police_record
    summary["police_record_2"] = d.police_record_2

    # Device extras
    summary["phone_assist"] = bool(d.phone_assist)

    # Invoicing / shifts
    summary["invoice_footer"] = d.invoice_footer
    summary["shift_reporting"] = bool(d.shift_reporting)
    summary["frequency"] = d.frequency
    summary["payment_terms"] = d.payment_terms
    summary["output_preference"] = d.output_preference
    summary["si_id"] = d.si_id

    # Payments / VAT
    summary["payment_on_day"] = d.payment_on_day
    summary["distribution"] = d.distribution
    summary["apply_vat"] = bool(d.apply_vat)
    summary["vat_rate"] = d.vat_rate
    summary["balance"] = d.balance
    summary["exclude_booking_fee"] = bool(d.exclude_booking_fee)
    summary["auto_post"] = d.auto_post
    summary["bank_payment_ref"] = d.bank_payment_ref
    summary["use_sepa"] = bool(d.use_sepa)
    summary["bank_name"] = d.bank_name
    summary["bank_account_name"] = d.bank_account_name
    summary["sort_code"] = d.sort_code
    summary["bank_account_number"] = d.bank_account_number

    # Breathalyser
    summary["breathalyser_enabled"] = bool(d.breathalyser_enabled)

    # Fatigue
    summary["fatigue_max_work_hours"] = d.fatigue_max_work_hours
    summary["fatigue_min_rest_hours"] = d.fatigue_min_rest_hours
    summary["fatigue_exceed_job_pct"] = d.fatigue_exceed_job_pct
    summary["fatigue_send_alert_pct"] = d.fatigue_send_alert_pct

    # Sites
    site_rows = db.query(DriverSite).filter(DriverSite.driver_id == d.id).all()
    summary["sites"] = [
        {
            "site_code": s.site_code,
            "site_name": s.site_name,
            "assigned": bool(s.assigned),
            "is_primary": bool(s.is_primary),
        }
        for s in site_rows
    ]
    # If no rows yet, still expose the catalog so the UI can render the table.
    if not site_rows:
        summary["sites"] = [
            {"site_code": code, "site_name": name, "assigned": False, "is_primary": False}
            for code, name in SITE_REGISTRY.items()
        ]

    # Files (HR-style uploads — separate from compliance docs)
    from ...db.models import DriverFile
    files = db.query(DriverFile).filter(DriverFile.driver_id == d.id).all()
    summary["files"] = [
        {
            "id": f.id,
            "type": f.file_type,
            "filename": f.filename,
            "content_type": f.content_type,
            "size_bytes": f.size_bytes,
            "uploaded_at": f.uploaded_at.isoformat() if f.uploaded_at else None,
        }
        for f in files
    ]

    completed_trips = db.query(Trip).filter(
        Trip.driver_id == d.id,
        Trip.status == "completed"
    ).all()
    commission = d.commission_rate if d.commission_rate is not None else 0.30
    total_earnings = sum((t.fare or 0) for t in completed_trips) * (1 - commission)
    summary["total_trips"] = len(completed_trips)
    summary["total_earnings"] = round(total_earnings, 2)

    from ...db.models import Document
    docs = db.query(Document).filter(
        Document.entity_id == d.id,
        Document.entity_type == "driver"
    ).all()
    summary["documents"] = [
        {
            "type": doc.doc_type,
            "status": doc.status,
            "expiry_date": doc.expiry_date.isoformat() if doc.expiry_date else None,
        }
        for doc in docs
    ]
    return summary
