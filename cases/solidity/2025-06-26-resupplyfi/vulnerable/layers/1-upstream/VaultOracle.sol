// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "../2-upstream/ShareVault.sol";

// Prices vault shares at their redemption value: the assets one whole share (1e18) converts to.
contract VaultOracle {
    function getPrice(ShareVault vault) external view returns (uint256 price) {
        price = vault.convertToAssets(1e18);
    }
}
