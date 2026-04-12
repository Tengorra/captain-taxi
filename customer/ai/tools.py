"""
Claude tool definitions for the customer service agent.

These tools are declared to Claude and handled in conversation.py.
"""

TOOLS = [
    {
        "name": "create_booking",
        "description": (
            "Create a taxi booking. Call this once you have all required details: "
            "pickup address, dropoff address, customer name, phone number."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pickup_address":  {"type": "string", "description": "Full street address for pickup"},
                "dropoff_address": {"type": "string", "description": "Full street address for dropoff"},
                "customer_name":   {"type": "string", "description": "Customer full name"},
                "customer_phone":  {"type": "string", "description": "Customer phone number with country code"},
                "num_passengers":  {"type": "integer", "description": "Number of passengers", "default": 1},
                "pickup_time":     {
                    "type": "string",
                    "description": "ISO 8601 datetime for scheduled pickup, or 'ASAP'",
                    "default": "ASAP"
                },
                "notes": {"type": "string", "description": "Any special requirements (WAV, luggage, etc.)"},
                "city": {
                    "type": "string",
                    "enum": ["saskatoon", "regina"],
                    "description": "City for the trip. Infer from addresses — default saskatoon.",
                    "default": "saskatoon",
                },
            },
            "required": ["pickup_address", "dropoff_address", "customer_name", "customer_phone"],
        },
    },
    {
        "name": "get_trip_status",
        "description": "Look up the status and ETA of an existing trip by trip ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "trip_id": {"type": "string", "description": "The trip/booking ID"},
            },
            "required": ["trip_id"],
        },
    },
    {
        "name": "cancel_trip",
        "description": "Cancel an existing booking by trip ID.",
        "input_schema": {
            "type": "object",
            "properties": {
                "trip_id": {"type": "string", "description": "The trip/booking ID to cancel"},
                "reason":  {"type": "string", "description": "Cancellation reason", "default": "Customer request"},
            },
            "required": ["trip_id"],
        },
    },
    {
        "name": "get_fare_estimate",
        "description": "Estimate the fare for a trip between two addresses.",
        "input_schema": {
            "type": "object",
            "properties": {
                "pickup_address":  {"type": "string"},
                "dropoff_address": {"type": "string"},
                "after_hours":     {"type": "boolean", "default": False},
            },
            "required": ["pickup_address", "dropoff_address"],
        },
    },
    {
        "name": "log_complaint",
        "description": (
            "Log a customer complaint. Use severity='minor' for service issues "
            "(lateness, cleanliness, rudeness). Use severity='serious' for safety incidents, "
            "harassment, or dangerous driving — these immediately alert the owner."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "description": {"type": "string", "description": "Full complaint description"},
                "severity":    {"type": "string", "enum": ["minor", "serious"]},
                "trip_id":     {"type": "string", "description": "Related trip ID if known"},
            },
            "required": ["description", "severity"],
        },
    },
    {
        "name": "lookup_customer_bookings",
        "description": "Look up recent bookings for a customer by phone number.",
        "input_schema": {
            "type": "object",
            "properties": {
                "customer_phone": {"type": "string"},
            },
            "required": ["customer_phone"],
        },
    },
]
