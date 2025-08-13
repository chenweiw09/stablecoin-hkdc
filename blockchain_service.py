import os
import json
from web3 import Web3

from dotenv import load_dotenv

# 加载 .env 文件中的环境变量
load_dotenv()

class BlockchainService:
    def __init__(self):
        self.w3 = Web3(Web3.HTTPProvider(os.getenv("SEPOLIA_RPC_URL")))
        if not self.w3.is_connected():
            raise ConnectionError("无法连接到以太坊节点")

        self.contract_address = Web3.to_checksum_address(os.getenv("HKDC_CONTRACT_ADDRESS"))
        self.hot_wallet_private_key = os.getenv("EXCHANGE_HOT_WALLET_PRIVATE_KEY")
        self.hot_wallet_address = self.w3.eth.account.from_key(self.hot_wallet_private_key).address

        with open('abi.json', 'r') as f:
            abi = json.load(f)
        self.contract = self.w3.eth.contract(address=self.contract_address, abi=abi)
        self.decimals = self.contract.functions.decimals().call()
        print("Blockchain Service Initialized.")
        print(f"Exchange Hot Wallet: {self.hot_wallet_address}")

    def _format_to_wei(self, amount: float) -> int:
        return int(amount * (10 ** self.decimals))

    def transfer_hkdc(self, recipient_address: str, amount: float):
        recipient_checksum = Web3.to_checksum_address(recipient_address)
        amount_in_wei = self._format_to_wei(amount)

        nonce = self.w3.eth.get_transaction_count(self.hot_wallet_address)
        tx_params = {'from': self.hot_wallet_address, 'nonce': nonce, 'gasPrice': self.w3.eth.gas_price}

        function_call = self.contract.functions.transfer(recipient_checksum, amount_in_wei)
        gas = function_call.estimate_gas({'from': self.hot_wallet_address})
        tx_params['gas'] = int(gas * 1.2)

        transaction = function_call.build_transaction(tx_params)
        signed_txn = self.w3.eth.account.sign_transaction(transaction, private_key=self.hot_wallet_private_key)
        tx_hash = self.w3.eth.send_raw_transaction(signed_txn.rawTransaction)
        return self.w3.eth.wait_for_transaction_receipt(tx_hash)