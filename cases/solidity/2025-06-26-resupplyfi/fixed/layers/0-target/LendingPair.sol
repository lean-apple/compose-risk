// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../1-upstream/VaultOracle.sol";

// Lending pair. Borrowers post vault shares as collateral and borrow the protocol's stablecoin,
// which the pair holds and treats as worth one vault asset each.
contract LendingPair {
    ShareVault public immutable collateral;
    Stablecoin public immutable debtToken;
    VaultOracle public immutable oracle;

    uint256 public constant EXCHANGE_PRECISION = 1e18;
    uint256 public constant LTV_PRECISION = 1e5;
    uint256 public constant MAX_LTV = 90_000;

    // Collateral shares per debt token, scaled by EXCHANGE_PRECISION.
    uint256 public exchangeRate;

    mapping(address => uint256) public collateralOf;
    mapping(address => uint256) public debtOf;

    constructor(ShareVault collateral_, Stablecoin debtToken_, VaultOracle oracle_) {
        collateral = collateral_;
        debtToken = debtToken_;
        oracle = oracle_;
    }

    function depositCollateral(uint256 shares) external {
        require(collateral.transferFrom(msg.sender, address(this), shares), "transfer failed");
        collateralOf[msg.sender] += shares;
    }

    function borrow(uint256 amount) external {
        _updateExchangeRate();
        debtOf[msg.sender] += amount;
        require(_isSolvent(msg.sender), "insolvent");
        require(debtToken.transfer(msg.sender, amount), "transfer failed");
    }

    function repay(uint256 amount) external {
        require(debtToken.transferFrom(msg.sender, address(this), amount), "transfer failed");
        debtOf[msg.sender] -= amount;
    }

    function withdrawCollateral(uint256 shares) external {
        _updateExchangeRate();
        collateralOf[msg.sender] -= shares;
        require(_isSolvent(msg.sender), "insolvent");
        require(collateral.transfer(msg.sender, shares), "transfer failed");
    }

    function _updateExchangeRate() internal {
        exchangeRate = 1e36 / oracle.getPrice(collateral);
    }

    function _isSolvent(address borrower) internal view returns (bool) {
        uint256 debt = debtOf[borrower];
        if (debt == 0) return true;
        uint256 shares = collateralOf[borrower];
        if (shares == 0) return false;
        uint256 ltv = (debt * exchangeRate * LTV_PRECISION / EXCHANGE_PRECISION) / shares;
        return ltv <= MAX_LTV;
    }
}
