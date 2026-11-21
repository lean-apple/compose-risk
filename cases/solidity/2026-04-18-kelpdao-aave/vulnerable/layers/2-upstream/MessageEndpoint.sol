// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "./EndpointConfig.sol";

interface IMessageReceiver {
    function receiveMessage(uint32 srcChain, bytes calldata payload) external;
}

// Cross-chain messaging endpoint.
// A message is delivered once `requiredConfirmations` registered verifiers confirm it.
contract MessageEndpoint {
    address public admin;
    mapping(address => bool) public isVerifier;
    uint256 public verifierCount;
    uint256 public requiredConfirmations;

    mapping(bytes32 => uint256) public confirmations;
    mapping(bytes32 => mapping(address => bool)) public confirmedBy;
    mapping(bytes32 => bool) public delivered;

    event Delivered(bytes32 indexed id, address indexed receiver);

    constructor(address[] memory verifiers) {
        require(verifiers.length == EndpointConfig.VERIFIER_COUNT, "wrong verifier count");
        admin = msg.sender;
        for (uint256 i = 0; i < verifiers.length; i++) {
            isVerifier[verifiers[i]] = true;
        }
        verifierCount = verifiers.length;
        requiredConfirmations = EndpointConfig.REQUIRED_CONFIRMATIONS;
    }

    function messageId(uint32 srcChain, uint64 nonce, address receiver, bytes calldata payload)
        public
        pure
        returns (bytes32)
    {
        return keccak256(abi.encode(srcChain, nonce, receiver, payload));
    }

    function confirm(uint32 srcChain, uint64 nonce, address receiver, bytes calldata payload) external {
        require(isVerifier[msg.sender], "not verifier");
        bytes32 id = messageId(srcChain, nonce, receiver, payload);
        require(!confirmedBy[id][msg.sender], "already confirmed");
        confirmedBy[id][msg.sender] = true;
        confirmations[id] += 1;
    }

    function deliver(uint32 srcChain, uint64 nonce, address receiver, bytes calldata payload) external {
        bytes32 id = messageId(srcChain, nonce, receiver, payload);
        require(!delivered[id], "already delivered");
        require(confirmations[id] >= requiredConfirmations, "not enough confirmations");
        delivered[id] = true;
        IMessageReceiver(receiver).receiveMessage(srcChain, payload);
        emit Delivered(id, receiver);
    }
}
