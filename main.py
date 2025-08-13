# main.py

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse  # <--- 1. 导入 FileResponse
from fastapi.staticfiles import StaticFiles # <--- 2. 导入 StaticFiles
import os
from sqlalchemy.orm import Session
from jose import JWTError, jwt
from typing import List
import models
import schemas
import database
import security
import crud
from web3.exceptions import TransactionNotFound


from blockchain_service import BlockchainService

# Create database tables
models.Base.metadata.create_all(bind=database.engine)

app = FastAPI(title="HKDC Exchange API")

# --- CORS 中间件 (保持不变) ---
origins = [
    "http://localhost",
    "http://localhost:8000",
    "http://127.0.0.1",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


static_file_path = os.path.join(os.path.dirname(__file__), "static")


app.mount("/static", StaticFiles(directory=static_file_path), name="static")


blockchain_service = BlockchainService()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(database.get_db)):
    credentials_exception = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Could not validate credentials", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        email: str = payload.get("sub")
        if email is None: raise credentials_exception
        user = crud.get_user_by_email(db, email=email)
        if user is None: raise credentials_exception
        return user
    except JWTError:
        raise credentials_exception

# --- 6. 新增：根路径路由，返回登录页面 ---
@app.get("/", include_in_schema=False)
async def read_root():
    """
    当用户访问根URL时，返回前端的 index.html 文件。
    """
    return FileResponse(os.path.join(static_file_path, "index.html"))

# 更新：注册接口
@app.post("/register", response_model=schemas.User, status_code=status.HTTP_201_CREATED)
def register_user(user: schemas.UserCreate, db: Session = Depends(database.get_db)):
    if crud.get_user_by_email(db, email=user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    return crud.create_user(db=db, user=user)


@app.post("/token", response_model=schemas.Token)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends(),
                                 db: Session = Depends(database.get_db)):
    user = crud.get_user_by_email(db, email=form_data.username)
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")

    access_token = security.create_access_token(data={"sub": user.email})
    return {"access_token": access_token, "token_type": "bearer"}

# 更新：获取用户信息的接口，现在返回 UserDetails 模型
@app.get("/users/me", response_model=schemas.UserDetails, summary="获取当前用户信息和余额")
def read_users_me(current_user: models.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    account = crud.get_account_by_user_id(db, user_id=current_user.id)
    return {
        "user": current_user,
        "account_balance": account.balance if account else 0.0
    }


# 新增：KYC 提交接口
@app.post("/users/me/kyc", response_model=schemas.User, summary="提交KYC信息以激活账户")
def submit_kyc(
        kyc_data: schemas.KYCSumbit,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(database.get_db)
):
    if current_user.status == 'active':
        raise HTTPException(status_code=400, detail="User is already active.")

    # --- 模拟活体检测服务 ---
    # 在真实世界中，这里会调用一个外部服务。我们直接模拟成功。
    liveness_check_passed = True
    if not liveness_check_passed:
        raise HTTPException(status_code=400, detail="Liveness check failed.")

    try:
        updated_user = crud.submit_kyc_info(db, user_id=current_user.id, kyc_data=kyc_data)
        if not updated_user:
            raise HTTPException(status_code=404, detail="User not found.")
        return updated_user
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.put("/users/me/activate", response_model=schemas.User, summary="[Simulation] Activate user after KYC")
def activate_user(current_user: schemas.User = Depends(get_current_user), db: Session = Depends(database.get_db)):
    if current_user.status == 'active':
        raise HTTPException(status_code=400, detail="User is already active")
    return crud.update_user_status(db, user_id=current_user.id, status='active')


@app.get("/deposit/alipay/info", summary="获取交易所支付宝收款信息")
def get_alipay_info(current_user: models.User = Depends(get_current_user)):
    """
    返回用于向用户展示的、交易所的支付宝收款账户信息。
    在真实世界中，这些信息应该来自安全的配置。
    """
    return {
        "account_name": "测试交易所账户名字",
        "account_id": "payment@quantum-ledger"
    }


@app.post("/deposit/alipay/confirm", summary="确认支付宝充值成功")
def confirm_alipay_deposit(
        request: schemas.DepositBankRequest,  # 我们复用这个schema来接收金额
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(database.get_db)
):
    """
    这是一个模拟的回调接口。
    在真实世界中，支付宝服务器会在用户支付成功后，异步通知这个接口。
    我们在这里为用户的内部账户增加余额。
    """
    # 检查用户状态等前置条件
    if current_user.status != 'active':
        raise HTTPException(status_code=403, detail="User is not active.")

    # 更新用户余额
    updated_account = crud.update_balance(db, user_id=current_user.id, amount=request.amount)

    # 创建详细的交易记录
    crud.create_transaction(
        db,
        initiator_user_id=current_user.id,
        type="deposit_alipay",
        amount=request.amount,
        status="completed"
    )

    return {
        "message": "Alipay deposit successful and credited.",
        "new_balance": updated_account.balance
    }

@app.get("/deposit/web3/address")
def get_web3_deposit_address():
    return {"deposit_address": blockchain_service.hot_wallet_address}

@app.post("/deposit/web3/confirm")
def confirm_web3_deposit(req: schemas.DepositBankRequest, user: schemas.User = Depends(get_current_user), db: Session = Depends(
    database.get_db)):
    crud.update_balance(db, user_id=user.id, amount=req.amount)
    crud.create_transaction(db, initiator_user_id=user.id, type="deposit_web3", amount=req.amount, status="completed")
    return {"message": "Web3 deposit confirmed"}


@app.post("/transfer", summary="执行内部转账")
def internal_transfer(
        request: schemas.TransferRequest,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(database.get_db)
):
    """
    执行用户间的内部转账，并增加对收款方的验证。
    """
    # 1. 验证发起方 (当前用户) 状态和余额
    if current_user.status != 'active':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is not active. Please complete KYC."
        )

    sender_account = crud.get_account_by_user_id(db, user_id=current_user.id)
    if not sender_account or sender_account.balance < request.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # 2. 验证收款方账户
    if request.recipient_email == current_user.email:
        raise HTTPException(status_code=400, detail="Cannot transfer to yourself.")

    recipient_user = crud.get_user_by_email(db, email=request.recipient_email)

    # 2a. 检查收款方账户是否存在
    if not recipient_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipient account does not exist."
        )

    # 2b. 检查收款方账户状态是否为 'active' (已认证)
    if recipient_user.status != 'active':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recipient account is at risk (not verified). Transfer aborted."
        )

    # 3. 执行转账操作 (如果所有验证都通过)
    crud.update_balance(db, user_id=current_user.id, amount=-request.amount)
    crud.update_balance(db, user_id=recipient_user.id, amount=request.amount)

    # 4. 创建详细的交易记录
    crud.create_transaction(
        db,
        initiator_user_id=current_user.id,
        recipient_user_id=recipient_user.id,
        type="internal_transfer",
        amount=request.amount,
        status="completed"
    )

    return {"message": "Transfer successful"}


@app.post("/withdraw/bank", summary="提现到指定的银行卡")
def withdraw_to_bank(
        request: schemas.WithdrawBankRequest,  # <-- 使用新的 Schema
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(database.get_db)
):
    # 1. 验证用户状态和余额 (保持不变)
    if current_user.status != 'active':
        raise HTTPException(status_code=403, detail="User is not active. Please complete KYC.")

    account = crud.get_account_by_user_id(db, user_id=current_user.id)
    if not account or account.balance < request.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance")

    # 2. 新增：验证银行卡是否属于当前用户
    bank_accounts = crud.get_bank_accounts_by_user_id(db, user_id=current_user.id)
    card_ids = [card.id for card in bank_accounts]
    if request.bank_account_id not in card_ids:
        raise HTTPException(status_code=403, detail="Bank account does not belong to the current user.")

    # 3. 执行扣款和记录
    crud.update_balance(db, user_id=current_user.id, amount=-request.amount)

    crud.create_transaction(
        db,
        initiator_user_id=current_user.id,
        type="withdraw_bank",
        amount=request.amount,
        bank_account_id=request.bank_account_id,  # <-- 记录提现的银行卡ID
        status="completed"
    )

    # 在真实应用中，这里会触发一个向银行打款的流程
    return {"message": "Bank withdrawal initiated successfully."}


@app.post("/withdraw/web3", summary="提现到指定的Web3钱包地址")
def withdraw_to_web3(
        request: schemas.WithdrawWeb3Request,  # 这个请求体包含 recipient_web3_address 和 amount
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(database.get_db)
):
    # 1. 前置验证：用户状态和余额 (符合要求)
    if current_user.status != 'active':
        raise HTTPException(status_code=403, detail="User is not active. KYC is required.")

    account = crud.get_account_by_user_id(db, user_id=current_user.id)
    if not account or account.balance < request.amount:
        raise HTTPException(status_code=400, detail="Insufficient balance.")

    # 2. 核心校验：后端检查用户输入的地址是否在全局白名单内 (符合要求)
    whitelisted_address = crud.get_whitelist_address_by_address(db, address=request.recipient_web3_address)

    # 2a. 检查地址是否存在于白名单
    if not whitelisted_address:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            # 前端会收到这个明确的错误信息
            detail="Withdrawal address is not in the exchange's whitelist. Transaction rejected."
        )

    # 2b. 检查白名单地址的状态是否正常
    if whitelisted_address.status == 'frozen':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            # 前端会收到这个明确的错误信息
            detail="This withdrawal address is currently frozen. Transaction rejected."
        )

    # 3. 执行区块链交易及后续操作 (符合要求)
    try:
        tx_receipt = blockchain_service.transfer_hkdc(request.recipient_web3_address, request.amount)
        tx_hash = tx_receipt.transactionHash.hex()

        crud.update_balance(db, user_id=current_user.id, amount=-request.amount)
        crud.create_transaction(
            db,
            initiator_user_id=current_user.id,
            type="withdraw_web3",
            amount=request.amount,
            recipient_web3_address=request.recipient_web3_address,
            tx_hash=tx_hash,
            status="completed"
        )

        return {"message": "Web3 withdrawal successful", "tx_hash": tx_hash}
    except Exception as e:
        crud.create_transaction(
            db, initiator_user_id=current_user.id, type="withdraw_web3",
            amount=request.amount, status="failed", recipient_web3_address=request.recipient_web3_address
        )
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")

@app.get("/transactions/history", response_model=List[schemas.TransactionDetail], summary="获取当前用户的交易历史")
def get_transaction_history(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(database.get_db)
):
    return crud.get_transactions_by_user_id(db, user_id=current_user.id)


@app.get("/users/me/bank-accounts", response_model=List[schemas.BankAccount], summary="获取当前用户绑定的银行卡列表")
def read_user_bank_accounts(
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(database.get_db)
):
    """
    获取当前登录用户所有已绑定的银行卡信息。
    """
    return crud.get_bank_accounts_by_user_id(db, user_id=current_user.id)


@app.post("/users/me/bank-accounts", response_model=schemas.BankAccount, status_code=status.HTTP_201_CREATED,
          summary="为当前用户添加新的银行卡")
def add_user_bank_account(
        bank_account: schemas.BankAccountCreate,
        current_user: models.User = Depends(get_current_user),
        db: Session = Depends(database.get_db)
):
    """
    为当前登录用户绑定一张新的银行卡。
    """
    # 检查用户是否已激活 (KYC通过)
    if current_user.status != 'active':
        raise HTTPException(status_code=403, detail="User is not active. Please complete KYC first.")

    # 检查卡号是否已被其他人绑定
    db_bank_account = crud.get_bank_account_by_card_number(db, card_number=bank_account.card_number)
    if db_bank_account:
        raise HTTPException(status_code=400, detail="Bank card number already registered.")

    return crud.create_bank_account(db=db, bank_account=bank_account, user_id=current_user.id)

@app.get("/admin/whitelist", response_model=List[schemas.WhitelistAddress], summary="[Admin] 获取全局提现地址白名单")
def read_global_whitelist(db: Session = Depends(database.get_db)):
    return crud.get_all_whitelist_addresses(db)

@app.post("/admin/whitelist", response_model=schemas.WhitelistAddress, status_code=status.HTTP_201_CREATED, summary="[Admin] 添加新地址到全局白名单")
def add_address_to_global_whitelist(
    whitelist_data: schemas.WhitelistAddressCreate,
    db: Session = Depends(database.get_db)
):
    if not whitelist_data.address.startswith("0x") or len(whitelist_data.address) != 42:
        raise HTTPException(status_code=400, detail="Invalid Ethereum address format.")
    if crud.get_whitelist_address_by_address(db, address=whitelist_data.address):
        raise HTTPException(status_code=400, detail="Address already in whitelist.")
    return crud.add_to_whitelist(db, whitelist_data=whitelist_data)

@app.put("/admin/whitelist/{address_id}/status", response_model=schemas.WhitelistAddress, summary="[Admin] 更新白名单地址状态")
def update_whitelist_status(
    address_id: int,
    status_update: schemas.WhitelistAddressStatusUpdate,
    db: Session = Depends(database.get_db)
):
    if status_update.status not in ['normal', 'frozen']:
        raise HTTPException(status_code=400, detail="Invalid status. Must be 'normal' or 'frozen'.")
    updated_address = crud.update_whitelist_address_status(db, address_id=address_id, status=status_update.status)
    if not updated_address:
        raise HTTPException(status_code=404, detail="Whitelist address not found.")
    return updated_address

# # --- 用于本地开发直接运行 ---
if __name__ == '__main__':
    import uvicorn
    # 这里的 "main:app" 字符串告诉 uvicorn：
    # - "main" 指的是 main.py 文件
    # - "app" 指的是在该文件中创建的 FastAPI 实例 `app = FastAPI()`
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)