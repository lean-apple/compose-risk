// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./Stablecoin.sol";

// ERC4626-style lending vault. Deposits mint shares at the current share price; the price is
// the vault's asset balance over its share supply, with virtual shares so that a donation to
// the vault cannot take value from later depositors.
contract ShareVault {
    Stablecoin public immutable asset;
    uint256 public constant VIRTUAL_SHARES = 1_000;

    uint256 public totalSupply;
    mapping(address => uint256) public balanceOf;
    mapping(address => mapping(address => uint256)) public allowance;

    constructor(Stablecoin asset_) {
        asset = asset_;
    }

    function totalAssets() public view returns (uint256) {
        return asset.balanceOf(address(this));
    }

    function convertToShares(uint256 assets) public view returns (uint256) {
        return assets * (totalSupply + VIRTUAL_SHARES) / (totalAssets() + 1);
    }

    function convertToAssets(uint256 shares) public view returns (uint256) {
        return shares * (totalAssets() + 1) / (totalSupply + VIRTUAL_SHARES);
    }

    function deposit(uint256 assets) external returns (uint256 shares) {
        shares = convertToShares(assets);
        require(shares > 0, "zero shares");
        require(asset.transferFrom(msg.sender, address(this), assets), "transfer failed");
        totalSupply += shares;
        balanceOf[msg.sender] += shares;
    }

    function redeem(uint256 shares) external returns (uint256 assets) {
        assets = convertToAssets(shares);
        require(balanceOf[msg.sender] >= shares, "balance");
        balanceOf[msg.sender] -= shares;
        totalSupply -= shares;
        require(asset.transfer(msg.sender, assets), "transfer failed");
    }

    function approve(address spender, uint256 amount) external returns (bool) {
        allowance[msg.sender][spender] = amount;
        return true;
    }

    function transfer(address to, uint256 amount) external returns (bool) {
        _move(msg.sender, to, amount);
        return true;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        uint256 allowed = allowance[from][msg.sender];
        require(allowed >= amount, "allowance");
        allowance[from][msg.sender] = allowed - amount;
        _move(from, to, amount);
        return true;
    }

    function _move(address from, address to, uint256 amount) internal {
        require(balanceOf[from] >= amount, "balance");
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
    }
}
