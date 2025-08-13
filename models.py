from sqlalchemy import Column, Integer, String, Float, ForeignKey, DateTime, func
from sqlalchemy.orm import relationship
from database import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    # 更新：允许姓名和身份证号在初始时为空
    full_name = Column(String, index=True, nullable=True)
    identity_card_number = Column(String, unique=True, index=True, nullable=True)
    hashed_password = Column(String, nullable=False)
    # 更新：初始状态为 unverified
    status = Column(String, default="unverified", nullable=False)

    account = relationship("Account", back_populates="owner", uselist=False, cascade="all, delete-orphan")
    bank_accounts = relationship("BankAccount", back_populates="owner", cascade="all, delete-orphan")

class Account(Base):
    __tablename__ = "accounts"
    id = Column(Integer, primary_key=True, index=True)
    balance = Column(Float, default=0.0)
    user_id = Column(Integer, ForeignKey("users.id"))
    owner = relationship("User", back_populates="account")


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)

    # Transaction Participants
    initiator_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    recipient_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)

    # Off-chain / On-chain Addresses
    initiator_web3_address = Column(String, nullable=True)
    recipient_web3_address = Column(String, nullable=True)
    bank_account_id = Column(Integer, ForeignKey("bank_accounts.id"), nullable=True)

    # Transaction Details
    type = Column(String, nullable=False)
    amount = Column(Float, nullable=False)
    tx_hash = Column(String, nullable=True, unique=True)

    # Status and Timestamps
    status = Column(String, default="pending", nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)

    # SQLAlchemy Relationships (for easy data loading)
    initiator = relationship("User", foreign_keys=[initiator_user_id])
    recipient = relationship("User", foreign_keys=[recipient_user_id])
    bank_account = relationship("BankAccount")


class BankAccount(Base):
    __tablename__ = "bank_accounts"
    id = Column(Integer, primary_key=True, index=True)
    account_name = Column(String, nullable=False) # 银行账户名 (持卡人姓名)
    bank_name = Column(String, nullable=False)    # 银行名称
    card_number = Column(String, unique=True, nullable=False) # 银行卡号，唯一
    user_id = Column(Integer, ForeignKey("users.id"))

    owner = relationship("User", back_populates="bank_accounts")


class WithdrawalWhitelist(Base):
    __tablename__ = "withdrawal_whitelist"
    id = Column(Integer, primary_key=True, index=True)
    address = Column(String, unique=True, index=True, nullable=False) # 地址必须唯一
    label = Column(String, nullable=False) # 标签，如 "Binance Hot Wallet"
    status = Column(String, default="normal", nullable=False) # 状态: normal, frozen
    frozen_at = Column(DateTime(timezone=True), nullable=True) # 冻结开始时间
