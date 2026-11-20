// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

// Verifier set size and confirmation threshold the endpoint is deployed with.
library EndpointConfig {
    uint256 internal constant VERIFIER_COUNT = 2;
    uint256 internal constant REQUIRED_CONFIRMATIONS = 2;
}
