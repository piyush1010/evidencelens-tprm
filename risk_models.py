"""Data structures for vendor intake and risk results. Standard library only."""

from dataclasses import asdict, dataclass, field
from typing import List, Optional

SENSITIVITY_LEVELS = ["Low", "Medium", "High"]
VOLUME_BANDS = ["Under 1,000 records", "1,000–100,000 records", "Over 100,000 records"]
REPLACEABILITY = ["Easy", "Moderate", "Hard"]
DATA_TYPES = [
    "Employee data", "Customer personal data", "Payment card data", "Bank account data",
    "Health data", "Authentication credentials", "Source code", "Confidential business data",
]
REGULATIONS = ["GDPR", "India DPDP Act", "HIPAA", "PCI DSS", "SOX", "GLBA"]
TIERS = ["Low", "Medium", "High", "Critical"]
RECOMMENDATIONS = [
    "Approve", "Approve with conditions", "Remediation required",
    "Escalate for risk acceptance", "Reject",
]


@dataclass
class VendorProfile:
    vendor_name: str
    service_description: str
    business_owner: str
    data_types: List[str] = field(default_factory=list)
    personal_data: bool = False
    financial_or_health_data: bool = False
    record_volume: str = VOLUME_BANDS[0]
    production_access: bool = False
    privileged_access: bool = False
    business_criticality: str = "Low"
    operational_dependency: str = "Low"
    uses_subprocessors: bool = False
    regulatory_exposure: List[str] = field(default_factory=list)
    replaceability: str = "Easy"

    def validate(self) -> List[str]:
        errors = []
        if not self.vendor_name.strip():
            errors.append("Vendor name is required.")
        if not self.service_description.strip():
            errors.append("Service description is required.")
        if not self.business_owner.strip():
            errors.append("Business owner is required.")
        if self.record_volume not in VOLUME_BANDS:
            errors.append("Choose a valid record volume.")
        for label, value in (("Business criticality", self.business_criticality),
                             ("Operational dependency", self.operational_dependency)):
            if value not in SENSITIVITY_LEVELS:
                errors.append(f"{label} must be Low, Medium or High.")
        if self.replaceability not in REPLACEABILITY:
            errors.append("Choose how easy the vendor is to replace.")
        unknown = [r for r in self.regulatory_exposure if r not in REGULATIONS]
        if unknown:
            errors.append(f"Unknown regulation(s): {', '.join(unknown)}.")
        sensitive_types = {"Payment card data", "Bank account data", "Health data"}
        if sensitive_types & set(self.data_types) and not self.financial_or_health_data:
            errors.append("Selected data types include financial or health data; tick that box.")
        personal_types = {"Employee data", "Customer personal data", "Health data"}
        if personal_types & set(self.data_types) and not self.personal_data:
            errors.append("Selected data types include personal data; tick that box.")
        return errors

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class RiskFactor:
    factor: str
    response: str
    points: int


@dataclass
class InherentRisk:
    score: int
    tier: str
    factors: List[RiskFactor]
    floor_applied: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ResidualRisk:
    inherent_tier: str
    residual_tier: str
    recommendation: str
    provisional: bool
    drivers: List[str]
    counts: dict

    def to_dict(self) -> dict:
        return asdict(self)
