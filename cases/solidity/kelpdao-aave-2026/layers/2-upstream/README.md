# 2-upstream: MessageEndpoint

Delivers a message once enough verifiers confirm it. `EndpointConfig.sol` deploys it with one verifier and one required confirmation, so that verifier alone can approve any message. This is where the root cause sits.

On Ethereum: LayerZero's [EndpointV2](https://etherscan.io/address/0x1a44076050125825900e736c501f859c50fe728c), the endpoint the rsETH adapter uses; the route was configured with a single verifier (DVN).
