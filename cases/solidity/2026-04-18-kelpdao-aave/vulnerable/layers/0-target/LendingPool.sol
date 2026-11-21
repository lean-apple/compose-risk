// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../1-upstream/BridgedRestakeToken.sol";

// Lending pool. Lenders supply ETH; borrowers post the bridged restaking token as collateral
// and borrow ETH against it.
contract LendingPool {
    BridgedRestakeToken public immutable collateralToken;
    address public immutable governance;

    uint256 public collateralPriceInEth; // 1e18 = 1 ETH per token, set by governance
    uint256 public constant LTV_BPS = 7_500;

    mapping(address => uint256) public supplied;
    uint256 public totalSupplied;
    uint256 public totalBorrowed;
    uint256 public insuranceFund;

    mapping(address => uint256) public collateralOf;
    mapping(address => uint256) public debtOf;

    constructor(BridgedRestakeToken token, uint256 priceInEth) payable {
        collateralToken = token;
        governance = msg.sender;
        collateralPriceInEth = priceInEth;
        insuranceFund = msg.value;
    }

    function setCollateralPrice(uint256 priceInEth) external {
        require(msg.sender == governance, "only governance");
        collateralPriceInEth = priceInEth;
    }

    function supplyEth() external payable {
        supplied[msg.sender] += msg.value;
        totalSupplied += msg.value;
    }

    function withdrawEth(uint256 amount) external {
        require(supplied[msg.sender] >= amount, "exceeds supply");
        require(availableLiquidity() >= amount, "insufficient liquidity");
        supplied[msg.sender] -= amount;
        totalSupplied -= amount;
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
    }

    function depositCollateral(uint256 amount) external {
        require(collateralToken.transferFrom(msg.sender, address(this), amount), "transfer failed");
        collateralOf[msg.sender] += amount;
    }

    function borrow(uint256 amount) external {
        uint256 limit = (collateralOf[msg.sender] * collateralPriceInEth / 1e18) * LTV_BPS / 10_000;
        require(debtOf[msg.sender] + amount <= limit, "undercollateralised");
        require(availableLiquidity() >= amount, "insufficient liquidity");
        debtOf[msg.sender] += amount;
        totalBorrowed += amount;
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "send failed");
    }

    function availableLiquidity() public view returns (uint256) {
        return totalSupplied - totalBorrowed;
    }

    receive() external payable {}
}
