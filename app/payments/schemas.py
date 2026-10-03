from pydantic import BaseModel, EmailStr, Field, field_validator

from app.common import validate_person_name


class CustomerInfo(BaseModel):
    name: str = Field(..., min_length=2)
    mobile: str = Field(..., min_length=10, max_length=15)
    email: EmailStr | None = None

    @field_validator("name")
    @classmethod
    def _real_name(cls, value: str) -> str:
        return validate_person_name(value)


class AddressInfo(BaseModel):
    line1: str
    line2: str | None = None
    landmark: str | None = None
    city: str
    state: str
    pincode: str
    country: str = "India"


class CartItemInput(BaseModel):
    product_id: str
    name: str
    price: float = Field(..., ge=0)
    quantity: int = Field(..., ge=1)
    image: str | None = None
    weight: str | None = None
    weight_grams: float | None = None
    variant_info: dict | None = None


class CheckoutPayload(BaseModel):
    customer: CustomerInfo
    address: AddressInfo
    items: list[CartItemInput] = Field(..., min_length=1)


class CreatePaymentOrderRequest(CheckoutPayload):
    promo_code: str | None = None
    meta_event_id: str | None = None
    meta_fbp: str | None = None
    meta_fbc: str | None = None


class CreatePaymentOrderResponse(BaseModel):
    provider: str = "payu"
    payment_id: str | None = None
    amount: float | int
    currency: str = "INR"
    # PayU hosted checkout
    payment_url: str | None = None
    payu: dict | None = None
    # Razorpay (legacy)
    razorpay_order_id: str | None = None
    key_id: str | None = None


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str | None = None
    razorpay_payment_id: str | None = None
    razorpay_signature: str | None = None
    meta_event_id: str | None = None
    meta_fbp: str | None = None
    meta_fbc: str | None = None


class RefundPaymentRequest(BaseModel):
    amount: float | None = Field(
        default=None, description="Optional partial refund in INR; omit for full refund"
    )
    reason: str | None = None


class PaymentResponse(BaseModel):
    id: str
    order_db_id: str | None = None
    razorpay_order_id: str | None = None
    razorpay_payment_id: str | None = None
    razorpay_refund_id: str | None = None
    amount: float
    currency: str
    status: str
    failure_reason: str | None = None
