from sqlalchemy.orm import Session, joinedload
import models
import schemas
import security
from datetime import datetime
from typing import Optional, List
import pytz

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()


# 更新：简化版 create_user
def create_user(db: Session, user: schemas.UserCreate):
    hashed_password = security.get_password_hash(user.password)
    # email 和 password 是仅有的必填项
    db_user = models.User(
        email=user.email,
        hashed_password=hashed_password
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)

    # 仍然为用户创建关联的资金账户
    db_account = models.Account(user_id=db_user.id, balance=0.0)
    db.add(db_account)
    db.commit()

    return db_user


# 新增：更新用户KYC信息并激活账户的函数
def submit_kyc_info(db: Session, user_id: int, kyc_data: schemas.KYCSumbit):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if not db_user:
        return None

    # 检查身份证号是否已被其他人注册
    existing_user_by_id_card = db.query(models.User).filter(
        models.User.identity_card_number == kyc_data.identity_card_number).first()
    if existing_user_by_id_card and existing_user_by_id_card.id != user_id:
        raise ValueError("Identity card number is already registered by another user.")

    # 更新用户信息
    db_user.full_name = kyc_data.full_name
    db_user.identity_card_number = kyc_data.identity_card_number
    db_user.status = 'active'  # KYC成功后，状态变为 active

    db.commit()
    db.refresh(db_user)
    return db_user

def update_user_status(db: Session, user_id: int, status: str):
    db_user = db.query(models.User).filter(models.User.id == user_id).first()
    if db_user:
        db_user.status = status
        db.commit()
        db.refresh(db_user)
    return db_user

def get_account_by_user_id(db: Session, user_id: int):
    return db.query(models.Account).filter(models.Account.user_id == user_id).first()

def update_balance(db: Session, user_id: int, amount: float):
    account = get_account_by_user_id(db, user_id)
    if account:
        account.balance += amount
        db.commit()
        db.refresh(account)
    return account


def create_transaction(
        db: Session,
        *,
        initiator_user_id: int,
        type: str,
        amount: float,
        status: str,
        recipient_user_id: Optional[int] = None,
        initiator_web3_address: Optional[str] = None,
        recipient_web3_address: Optional[str] = None,
        tx_hash: Optional[str] = None,
        bank_account_id: Optional[int] = None
) -> models.Transaction:
    tx_data = {
        'initiator_user_id': initiator_user_id,
        'type': type,
        'amount': amount,
        'status': status,
        'recipient_user_id': recipient_user_id,
        'initiator_web3_address': initiator_web3_address,
        'recipient_web3_address': recipient_web3_address,
        'tx_hash': tx_hash,
        'bank_account_id': bank_account_id
    }

    # Set completion timestamp only if the transaction is completed
    if status == 'completed':
        tx_data['completed_at'] = datetime.utcnow()

    # Create the SQLAlchemy model instance
    db_transaction = models.Transaction(**tx_data)

    # Add to session, commit to save, and refresh to get new state
    db.add(db_transaction)
    db.commit()
    db.refresh(db_transaction)

    return db_transaction


def get_transactions_by_user_id(db: Session, user_id: int):
    transactions_from_db = db.query(models.Transaction).options(
        joinedload(models.Transaction.initiator),
        joinedload(models.Transaction.recipient),
        joinedload(models.Transaction.bank_account)
    ).filter(
        (models.Transaction.initiator_user_id == user_id) |
        (models.Transaction.recipient_user_id == user_id)
    ).order_by(models.Transaction.created_at.desc()).all()

    # 定义目标时区 (东八区)
    target_timezone = pytz.timezone('Asia/Shanghai')

    # 手动构建响应列表，以便进行数据处理
    formatted_transactions = []
    for tx in transactions_from_db:
        # 对银行卡号进行脱敏处理 (保持不变)
        bank_account_info = None
        if tx.bank_account:
            card_num = tx.bank_account.card_number
            formatted_card_num = f"**** **** **** {card_num[-4:]}" if len(card_num) > 4 else card_num
            bank_account_info = {
                "bank_name": tx.bank_account.bank_name,
                "card_number": formatted_card_num
            }

        # 1. 将数据库取出的时间附加 UTC 时区信息
        created_at_utc = pytz.utc.localize(tx.created_at)

        # 2. 转换为东八区时间
        created_at_local = created_at_utc.astimezone(target_timezone)

        completed_at_local_str = '处理中...'
        if tx.completed_at:
            completed_at_utc = pytz.utc.localize(tx.completed_at)
            completed_at_local = completed_at_utc.astimezone(target_timezone)
            completed_at_local_str = completed_at_local.strftime('%Y/%m/%d %H:%M:%S')

        # 构建 Pydantic 模型期望的字典结构
        tx_data = {
            "id": tx.id,
            "type": tx.type,
            "amount": tx.amount,
            "status": tx.status,
            "created_at": created_at_local.strftime('%Y/%m/%d %H:%M:%S'),
            "completed_at": completed_at_local_str,
            "initiator": tx.initiator, # SQLAlchemy 关系对象可以直接被 Pydantic 模型使用
            "recipient": tx.recipient,
            "bank_account": bank_account_info, # 使用我们处理过的字典
            "recipient_web3_address": tx.recipient_web3_address,
            "tx_hash": tx.tx_hash,
        }
        formatted_transactions.append(tx_data)

    return formatted_transactions

def get_bank_account_by_card_number(db: Session, card_number: str):
    return db.query(models.BankAccount).filter(models.BankAccount.card_number == card_number).first()

def get_bank_accounts_by_user_id(db: Session, user_id: int):
    return db.query(models.BankAccount).filter(models.BankAccount.user_id == user_id).all()

def create_bank_account(db: Session, bank_account: schemas.BankAccountCreate, user_id: int):
    db_bank_account = models.BankAccount(**bank_account.dict(), user_id=user_id)
    db.add(db_bank_account)
    db.commit()
    db.refresh(db_bank_account)
    return db_bank_account


def get_whitelist_address_by_address(db: Session, address: str):
    return db.query(models.WithdrawalWhitelist).filter(models.WithdrawalWhitelist.address == address).first()


def get_all_whitelist_addresses(db: Session):
    return db.query(models.WithdrawalWhitelist).all()


def add_to_whitelist(db: Session, whitelist_data: schemas.WhitelistAddressCreate):
    db_address = models.WithdrawalWhitelist(**whitelist_data.dict())
    db.add(db_address)
    db.commit()
    db.refresh(db_address)
    return db_address


def update_whitelist_address_status(db: Session, address_id: int, status: str):
    db_address = db.query(models.WithdrawalWhitelist).filter(models.WithdrawalWhitelist.id == address_id).first()
    if not db_address:
        return None

    db_address.status = status
    if status == 'frozen':
        db_address.frozen_at = datetime.utcnow()
    else:  # normal
        db_address.frozen_at = None

    db.commit()
    db.refresh(db_address)
    return db_address