from datetime import date, datetime

from pydantic import BaseModel


class DealOrderBrief(BaseModel):
    id: str
    title: str
    content_description: str | None = None


class DealCreatorBrief(BaseModel):
    id: str
    name: str | None = None
    avatar_url: str | None = None


class DealAdvertiserBrief(BaseModel):
    id: str
    company_name: str | None = None
    logo_url: str | None = None


class DealListItem(BaseModel):
    id: str
    order: DealOrderBrief
    creator: DealCreatorBrief
    advertiser: DealAdvertiserBrief
    budget: int
    currency: str = "KZT"
    deadline: date
    conditions: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    video_count: int | None = None
    status: str
    created_at: datetime


class DealListResponse(BaseModel):
    data: list[DealListItem]


class SignatureItem(BaseModel):
    user_id: str
    name: str | None = None
    role: str | None = None
    status: str
    signed_at: datetime | None = None


class ContractInfo(BaseModel):
    terms: str = "Подписывая, обе стороны соглашаются с условиями сотрудничества через платформу AddSy."
    signatures: list[SignatureItem] = []


class WorkRequirementItem(BaseModel):
    id: str
    label: str
    is_completed: bool = False


class SubmittedWorkItem(BaseModel):
    id: str
    title: str
    file_url: str
    duration: str | None = None
    format: str | None = None
    uploaded_at: datetime


class PayoutInfo(BaseModel):
    budget: int
    platform_fee: int
    creator_payout: int
    currency: str = "KZT"


class DealDetail(DealListItem):
    contract: ContractInfo | None = None
    work_requirements: list[WorkRequirementItem] = []
    submitted_work: list[SubmittedWorkItem] = []
    escrow_amount: int = 0
    platform_fee: int = 0
    creator_payout: int = 0
    payment_status: str = "pending"
    work_submitted_at: datetime | None = None
    dispute_reason: str | None = None


# --- Request/Response for sign flow ---

class RequestSignResponse(BaseModel):
    deal_id: str
    message: str = "SMS-код отправлен"


class SignDealRequest(BaseModel):
    code: str


class SignDealResponse(BaseModel):
    deal_id: str
    signature_status: str
    deal_status: str


# --- Payment ---

class PayDealRequest(BaseModel):
    payment_method: str = "kaspi"


class PaymentInfo(BaseModel):
    amount: int
    currency: str = "KZT"
    method: str
    paid_at: datetime


class PayDealResponse(BaseModel):
    deal_id: str
    status: str
    escrow_amount: int
    payment: PaymentInfo


# --- Work submission ---

class SubmitWorkResponse(BaseModel):
    deal_id: str
    status: str
    work_submitted_at: datetime | None = None
    submitted_work: list[SubmittedWorkItem] = []


# --- Confirm / Accept work ---

class ConfirmWorkResponse(BaseModel):
    deal_id: str
    status: str
    payout: PayoutInfo


# --- Dispute ---

class DisputeDealRequest(BaseModel):
    reason: str


class DisputeDealResponse(BaseModel):
    deal_id: str
    status: str
    reason: str


# --- Accept work (legacy alias) ---

class AcceptWorkResponse(BaseModel):
    deal_id: str
    status: str
