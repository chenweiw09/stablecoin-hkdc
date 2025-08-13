from pydantic import BaseModel, EmailStr, constr, Field
from typing import Optional, List
from datetime import datetime


# 更新：简化注册模型
class UserCreate(BaseModel):
    email: EmailStr
    password: constr(min_length=8)

# 新增：KYC提交模型
class KYCSumbit(BaseModel):
    full_name: str
    identity_card_number: str

# 更新：User返回模型，允许部分字段为空
class User(BaseModel):
    id: int
    email: EmailStr
    full_name: Optional[str]
    identity_card_number: Optional[str]
    status: str
    class Config:
        orm_mode = True

# --- 新增：专门用于 /users/me 响应的模型 ---
# 这样可以清晰地将用户信息和账户余额组合在一起
class UserDetails(BaseModel):
    user: User
    account_balance: float


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    email: Optional[EmailStr] = None


class DepositBankRequest(BaseModel):
    amount: float = Field(..., gt=0)


class TransferRequest(BaseModel):
    recipient_email: EmailStr
    amount: float = Field(..., gt=0)


class WithdrawRequest(BaseModel):
    amount: float = Field(..., gt=0)


class WithdrawWeb3Request(BaseModel):
    amount: float = Field(..., gt=0)
    recipient_web3_address: str


# --- Helper Schemas for Nested Responses ---
class UserInfo(BaseModel):
    email: str
    full_name: Optional[str]

    class Config:
        orm_mode = True


class BankAccountInfo(BaseModel):
    bank_name: str
    card_number: str

    class Config:
        orm_mode = True


# --- Transaction Detail Schema for API Responses ---
class TransactionDetail(BaseModel):
    id: int
    type: str
    amount: float
    status: str
    created_at: str
    completed_at: Optional[str]

    # Nested User Information
    initiator: UserInfo
    recipient: Optional[UserInfo]

    # Withdrawal Details
    bank_account: Optional[BankAccountInfo]
    recipient_web3_address: Optional[str]
    tx_hash: Optional[str]

    class Config:
        orm_mode = True

class BankAccountBase(BaseModel):
    account_name: str
    bank_name: str
    card_number: str

class BankAccountCreate(BankAccountBase):
    pass

class BankAccount(BankAccountBase):
    id: int
    user_id: int

    class Config:
        orm_mode = True

class WithdrawBankRequest(BaseModel):
    amount: float = Field(..., gt=0)
    bank_account_id: int

# --- 重构：提现地址白名单相关的 Schemas ---
class WhitelistAddressBase(BaseModel):
    label: str
    address: str

class WhitelistAddressCreate(WhitelistAddressBase):
    pass

class WhitelistAddress(WhitelistAddressBase):
    id: int
    status: str
    frozen_at: Optional[datetime]
    class Config:
        orm_mode = True

# 新增：用于更新白名单地址状态的 Schema
class WhitelistAddressStatusUpdate(BaseModel):
    status: str = Field(..., description="状态: 'normal' or 'frozen'")