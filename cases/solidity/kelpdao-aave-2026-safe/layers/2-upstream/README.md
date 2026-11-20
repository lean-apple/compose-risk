# 2-upstream: MessageEndpoint

Delivers a message once enough verifiers confirm it. `EndpointConfig.sol` deploys it with two verifiers and two required confirmations, so a single compromised verifier cannot approve a message.
