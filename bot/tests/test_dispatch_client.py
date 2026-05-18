"""Unit tests for the dispatch client helpers."""
import pytest

from services import dispatch_client
from services.dispatch_client import DispatchError, infer_city


# ── City inference ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "pickup,dropoff,expected",
    [
        ("224 Idylwyld Dr N, Saskatoon", "City Hospital, Saskatoon", "saskatoon"),
        ("100 Main St, Warman", "Saskatoon airport", "saskatoon"),
        ("500 Victoria Ave, Regina", "Regina airport", "regina"),
        ("White City", "Emerald Park", "regina"),
        ("Pilot Butte", "Lumsden", "regina"),
        # Unknown → defaults to saskatoon
        ("somewhere", "elsewhere", "saskatoon"),
    ],
)
def test_infer_city(pickup, dropoff, expected):
    assert infer_city(pickup, dropoff) == expected


# ── create_trip payload + error handling ────────────────────────────────────


class _StubResponse:
    def __init__(self, status_code: int, json_body=None, text: str = ""):
        self.status_code = status_code
        self._json = json_body or {}
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            import httpx
            request = httpx.Request("POST", "http://stub")
            response = httpx.Response(self.status_code, text=self.text, request=request)
            raise httpx.HTTPStatusError("err", request=request, response=response)

    def json(self):
        return self._json


class _StubClient:
    """Minimal async-context-manager stand-in for httpx.AsyncClient."""

    def __init__(self, response: _StubResponse):
        self._response = response
        self.last_url = None
        self.last_json = None
        self.last_headers = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, json=None, headers=None):
        self.last_url = url
        self.last_json = json
        self.last_headers = headers
        return self._response

    async def get(self, url, headers=None):
        self.last_url = url
        self.last_headers = headers
        return self._response


@pytest.mark.asyncio
async def test_create_trip_normalises_id_and_city(monkeypatch):
    stub = _StubClient(_StubResponse(200, {"id": "trip-123", "status": "pending"}))
    monkeypatch.setattr(
        dispatch_client.httpx, "AsyncClient", lambda *a, **k: stub
    )

    result = await dispatch_client.create_trip(
        customer_phone="+15550001234",
        customer_name="Test",
        pickup_address="224 Idylwyld Dr N, Saskatoon",
        dropoff_address="City Hospital",
        notes="bot test",
    )

    assert result["trip_id"] == "trip-123"
    assert stub.last_url.endswith("/dispatch/trip")
    assert stub.last_json["booking_source"] == "bot"
    assert stub.last_json["city"] == "saskatoon"
    assert stub.last_json["customer_phone"] == "+15550001234"


@pytest.mark.asyncio
async def test_create_trip_respects_explicit_city(monkeypatch):
    stub = _StubClient(_StubResponse(200, {"id": "t-1"}))
    monkeypatch.setattr(dispatch_client.httpx, "AsyncClient", lambda *a, **k: stub)

    await dispatch_client.create_trip(
        customer_phone="+15550001234",
        customer_name="Test",
        pickup_address="Main St, Saskatoon",  # would infer saskatoon
        dropoff_address="Other",
        city="REGINA",  # explicit wins, normalised to lowercase
    )

    assert stub.last_json["city"] == "regina"


@pytest.mark.asyncio
async def test_create_trip_raises_on_http_error(monkeypatch):
    stub = _StubClient(_StubResponse(500, text="boom"))
    monkeypatch.setattr(dispatch_client.httpx, "AsyncClient", lambda *a, **k: stub)

    with pytest.raises(DispatchError):
        await dispatch_client.create_trip(
            customer_phone="+15550001234",
            customer_name="Test",
            pickup_address="A",
            dropoff_address="B",
        )
