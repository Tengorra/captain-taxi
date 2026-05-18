import enum
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Text, Enum as SAEnum,
    ForeignKey, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from database import Base


class DriverStatus(str, enum.Enum):
    ONBOARDING = "onboarding"
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class City(str, enum.Enum):
    SASKATOON = "saskatoon"
    REGINA = "regina"


class OnboardingStepName(str, enum.Enum):
    PERSONAL_INFO = "personal_info"
    SIN = "sin"
    DRIVERS_LICENSE = "drivers_license"
    LICENSE_ABSTRACT = "license_abstract"
    SGI_INSURANCE = "sgi_insurance"
    TAXI_LICENSE = "taxi_license"
    CRIMINAL_CHECK = "criminal_check"
    VEHICLE_INSPECTION = "vehicle_inspection"
    BANK_INFO = "bank_info"


class DocumentType(str, enum.Enum):
    DRIVERS_LICENSE = "drivers_license"
    LICENSE_ABSTRACT = "license_abstract"
    SGI_INSURANCE = "sgi_insurance"
    TAXI_LICENSE = "taxi_license"
    CRIMINAL_CHECK = "criminal_check"
    VEHICLE_INSPECTION = "vehicle_inspection"
    OTHER = "other"


ONBOARDING_STEPS_ORDERED = [
    OnboardingStepName.PERSONAL_INFO,
    OnboardingStepName.SIN,
    OnboardingStepName.DRIVERS_LICENSE,
    OnboardingStepName.LICENSE_ABSTRACT,
    OnboardingStepName.SGI_INSURANCE,
    OnboardingStepName.TAXI_LICENSE,
    OnboardingStepName.CRIMINAL_CHECK,
    OnboardingStepName.VEHICLE_INSPECTION,
    OnboardingStepName.BANK_INFO,
]

STEP_LABELS = {
    OnboardingStepName.PERSONAL_INFO: "Personal Information",
    OnboardingStepName.SIN: "Social Insurance Number",
    OnboardingStepName.DRIVERS_LICENSE: "Driver's License Upload",
    OnboardingStepName.LICENSE_ABSTRACT: "Driver's Abstract (SGI)",
    OnboardingStepName.SGI_INSURANCE: "SGI Vehicle Insurance",
    OnboardingStepName.TAXI_LICENSE: "City Taxi License",
    OnboardingStepName.CRIMINAL_CHECK: "Criminal Record Check",
    OnboardingStepName.VEHICLE_INSPECTION: "Vehicle Inspection Report",
    OnboardingStepName.BANK_INFO: "Bank Information (Direct Deposit)",
}


class Driver(Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    # Identity
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # E.164 format
    sin: Mapped[Optional[str]] = mapped_column(String(20))  # stored encrypted in prod
    address: Mapped[Optional[str]] = mapped_column(String(500))
    city: Mapped[City] = mapped_column(SAEnum(City))

    # Status
    status: Mapped[DriverStatus] = mapped_column(
        SAEnum(DriverStatus), default=DriverStatus.ONBOARDING
    )
    onboarding_completion: Mapped[float] = mapped_column(Float, default=0.0)  # 0.0–1.0

    # Vehicle
    vehicle_make: Mapped[Optional[str]] = mapped_column(String(100))
    vehicle_model: Mapped[Optional[str]] = mapped_column(String(100))
    vehicle_year: Mapped[Optional[int]] = mapped_column(Integer)
    vehicle_plate: Mapped[Optional[str]] = mapped_column(String(20))
    vehicle_color: Mapped[Optional[str]] = mapped_column(String(50))

    # iCabbi import fields
    icabbi_ref: Mapped[Optional[str]] = mapped_column(String(50), index=True)
    aka: Mapped[Optional[str]] = mapped_column(String(100))
    sex: Mapped[Optional[str]] = mapped_column(String(10))
    badge_number: Mapped[Optional[str]] = mapped_column(String(50))
    badge_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime)
    badge_type: Mapped[Optional[str]] = mapped_column(String(50))
    licence_number: Mapped[Optional[str]] = mapped_column(String(50))
    licence_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    commission_rate: Mapped[Optional[float]] = mapped_column(Float, default=0.30)
    driver_type: Mapped[Optional[str]] = mapped_column(String(50), default="regular")
    payment_type: Mapped[Optional[str]] = mapped_column(String(50), default="cash")

    # Bank (store only last 4 + transit/institution for display; full info encrypted)
    bank_institution: Mapped[Optional[str]] = mapped_column(String(50))
    bank_transit: Mapped[Optional[str]] = mapped_column(String(20))
    bank_account_last4: Mapped[Optional[str]] = mapped_column(String(10))

    # Flags
    is_available: Mapped[bool] = mapped_column(Boolean, default=False)
    onboarding_reminder_count: Mapped[int] = mapped_column(Integer, default=0)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    # Relationships
    onboarding_steps: Mapped[list["OnboardingStep"]] = relationship(
        back_populates="driver", cascade="all, delete-orphan"
    )
    documents: Mapped[list["DriverDocument"]] = relationship(
        back_populates="driver", cascade="all, delete-orphan"
    )
    metrics: Mapped[list["DriverMetrics"]] = relationship(
        back_populates="driver", cascade="all, delete-orphan"
    )
    flags: Mapped[list["PerformanceFlag"]] = relationship(
        back_populates="driver", cascade="all, delete-orphan"
    )
    complaints: Mapped[list["Complaint"]] = relationship(
        back_populates="driver", cascade="all, delete-orphan"
    )
    messages: Mapped[list["Message"]] = relationship(
        back_populates="driver", cascade="all, delete-orphan"
    )
    suspensions: Mapped[list["DriverSuspension"]] = relationship(
        back_populates="driver", cascade="all, delete-orphan"
    )
    termination: Mapped[Optional["DriverTermination"]] = relationship(
        back_populates="driver", uselist=False
    )
    availabilities: Mapped[list["DriverAvailability"]] = relationship(
        back_populates="driver", cascade="all, delete-orphan"
    )
    shift_assignments: Mapped[list["ShiftAssignment"]] = relationship(
        back_populates="driver", cascade="all, delete-orphan"
    )

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"


class OnboardingStep(Base):
    __tablename__ = "onboarding_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    step: Mapped[OnboardingStepName] = mapped_column(SAEnum(OnboardingStepName))
    completed: Mapped[bool] = mapped_column(Boolean, default=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    notes: Mapped[Optional[str]] = mapped_column(Text)
    data: Mapped[Optional[dict]] = mapped_column(JSON)  # step-specific data

    driver: Mapped["Driver"] = relationship(back_populates="onboarding_steps")


class DriverDocument(Base):
    __tablename__ = "driver_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    driver_id: Mapped[int] = mapped_column(ForeignKey("drivers.id"), index=True)
    doc_type: Mapped[DocumentType] = mapped_column(SAEnum(DocumentType))
    filename: Mapped[str] = mapped_column(String(255))
    storage_path: Mapped[str] = mapped_column(String(500))  # local or S3 path
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    verified: Mapped[bool] = mapped_column(Boolean, default=False)
    verified_by: Mapped[Optional[str]] = mapped_column(String(100))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    driver: Mapped["Driver"] = relationship(back_populates="documents")
