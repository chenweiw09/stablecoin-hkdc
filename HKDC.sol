// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";

interface IERC20 {
    function totalSupply() external view returns (uint256);
    function balanceOf(address account) external view returns (uint256);
    function allowance(address owner_, address spender) external view returns (uint256);
    function approve(address spender, uint256 amount) external returns (bool);
    function transfer(address to, uint256 amount) external returns (bool);
    function transferFrom(address from, address to, uint256 amount) external returns (bool);

    event Transfer(address indexed from, address indexed to, uint256 value);
    event Approval(address indexed owner_, address indexed spender, uint256 value);
}

contract HKDC is IERC20, Ownable {
    string public constant name = "HKDC Stablecoin";
    string public constant symbol = "HKDC";
    uint8 public constant decimals = 6;

    uint256 private _totalSupply;
    mapping(address => uint256) private _balances;
    mapping(address => mapping(address => uint256)) private _allowances;

    bool public whitelistEnabled;
    mapping(address => bool) private _whitelist;
    address[] private _whitelistArray;

    event WhitelistEnabled(bool enabled);
    event AddedToWhitelist(address indexed account);
    event RemovedFromWhitelist(address indexed account);
    event BatchWhitelistUpdated(uint256 added, uint256 removed);

    constructor(address initialOwner) Ownable(initialOwner) {
        // 初始化，给owner铸造100万HKDC
        uint256 initialAmount = 1_000_000 * 10 ** decimals;
        _mint(initialOwner, initialAmount);
    }

    // -------- ERC20 标准接口 --------
    function totalSupply() external view override returns (uint256) {
        return _totalSupply;
    }

    function balanceOf(address account) external view override returns (uint256) {
        return _balances[account];
    }

    function allowance(address owner_, address spender) external view override returns (uint256) {
        return _allowances[owner_][spender];
    }

    function approve(address spender, uint256 amount) external override returns (bool) {
        _approve(msg.sender, spender, amount);
        return true;
    }

    function transfer(address to, uint256 amount) external override returns (bool) {
        _transfer(msg.sender, to, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external override returns (bool) {
        uint256 currentAllowance = _allowances[from][msg.sender];
        if (currentAllowance != type(uint256).max) {
            require(currentAllowance >= amount, "ERC20: transfer amount exceeds allowance");
            _approve(from, msg.sender, currentAllowance - amount);
        }
        _transfer(from, to, amount);
        return true;
    }

    // -------- 铸币和销毁（owner权限） --------
    function mint(address to, uint256 amount) external onlyOwner {
        _mint(to, amount);
    }

    function burn(address from, uint256 amount) external onlyOwner {
        _burn(from, amount);
    }

    // -------- 白名单管理 --------
    function isWhitelisted(address account) public view returns (bool) {
        return _whitelist[account];
    }

    function setWhitelistEnabled(bool enabled) external onlyOwner {
        whitelistEnabled = enabled;
        emit WhitelistEnabled(enabled);
    }

    function addToWhitelist(address account) external onlyOwner {
        require(account != address(0), "HKDC: zero address");
        if (!_whitelist[account]) {
            _whitelist[account] = true;
            _whitelistArray.push(account);
            emit AddedToWhitelist(account);
        }
    }

    function removeFromWhitelist(address account) external onlyOwner {
        if (_whitelist[account]) {
            _whitelist[account] = false;
            for (uint i = 0; i < _whitelistArray.length; i++) {
                if (_whitelistArray[i] == account) {
                    _whitelistArray[i] = _whitelistArray[_whitelistArray.length - 1];
                    _whitelistArray.pop();
                    break;
                }
            }
            emit RemovedFromWhitelist(account);
        }
    }

    function batchUpdateWhitelist(address[] calldata toAdd, address[] calldata toRemove) external onlyOwner {
        uint256 added;
        uint256 removed;
        for (uint i = 0; i < toAdd.length; i++) {
            address a = toAdd[i];
            if (a != address(0) && !_whitelist[a]) {
                _whitelist[a] = true;
                _whitelistArray.push(a);
                added++;
            }
        }
        for (uint i = 0; i < toRemove.length; i++) {
            address a = toRemove[i];
            if (_whitelist[a]) {
                _whitelist[a] = false;
                for (uint j = 0; j < _whitelistArray.length; j++) {
                    if (_whitelistArray[j] == a) {
                        _whitelistArray[j] = _whitelistArray[_whitelistArray.length - 1];
                        _whitelistArray.pop();
                        break;
                    }
                }
                removed++;
            }
        }
        emit BatchWhitelistUpdated(added, removed);
    }

    function getwhitelist() external view returns(address[] memory) {
        return _whitelistArray;
    }

    // -------- 内部核心逻辑 --------
    function _transfer(address from, address to, uint256 amount) internal {
        require(from != address(0), "HKDC: transfer from zero");
        require(to != address(0), "HKDC: transfer to zero");
        require(_balances[from] >= amount, "HKDC: transfer amount exceeds balance");

        if (whitelistEnabled) {
            address ownerAddr = owner();
            if (from != ownerAddr && to != ownerAddr) {
                require(_whitelist[from], "HKDC: sender not whitelisted");
                require(_whitelist[to], "HKDC: recipient not whitelisted");
            }
        }

        unchecked {
            _balances[from] -= amount;
            _balances[to] += amount;
        }
        emit Transfer(from, to, amount);
    }

    function _mint(address to, uint256 amount) internal {
        require(to != address(0), "HKDC: mint to zero");
        _totalSupply += amount;
        unchecked {
            _balances[to] += amount;
        }
        emit Transfer(address(0), to, amount);
    }

    function _burn(address from, uint256 amount) internal {
        require(from != address(0), "HKDC: burn from zero");
        require(_balances[from] >= amount, "HKDC: burn amount exceeds balance");
        unchecked {
            _balances[from] -= amount;
            _totalSupply -= amount;
        }
        emit Transfer(from, address(0), amount);
    }

    function _approve(address owner_, address spender, uint256 amount) internal {
        require(owner_ != address(0), "HKDC: approve from zero");
        require(spender != address(0), "HKDC: approve to zero");
        _allowances[owner_][spender] = amount;
        emit Approval(owner_, spender, amount);
    }
}
