# KelpDAO → Aave (April 2026)

- **LendingPool** lends ETH against a bridged token used as collateral.
- **BridgedRestakeToken** mints tokens whenever the endpoint delivers a message.
- **MessageEndpoint** delivers a message once enough verifiers confirm it; here, one is enough.

Each contract is correct on its own. Together, the pool trusts collateral whose supply depends on a single verifier two layers away, so one compromised verifier can mint unbacked tokens and borrow every lender's ETH.

## What happened

On April 18, 2026, KelpDAO's rsETH route on LayerZero relied on a single verifier. By tampering with the RPC data that verifier read and taking down an external RPC provider, the attacker got it to attest a forged message, and the Ethereum adapter released 116,500 rsETH with nothing burned on the source chain. The attacker deposited 89,567 of them on Aave and borrowed about $190M of ETH, leaving Aave with an estimated $124M to $230M of bad debt and a rush of withdrawals. The mock mints new tokens where the real adapter released existing ones; the trust gap is the same.

Afterwards, LayerZero stopped signing for single-verifier routes and moved its defaults to several verifiers, KelpDAO moved rsETH to Chainlink CCIP, and Aave froze the rsETH markets.

Sources: [LayerZero incident report](https://layerzero.network/blog/layerzero-labs-kelpdao-incident-report), [Aave incident report](https://governance.aave.com/t/rseth-incident-report-april-20-2026/24580), [KelpDAO's move to CCIP](https://www.theblock.co/news/ecosystems/2026-05-05-kelp-dao-ditches-layerzero-chainlink-cross-chain-infrastructure-292-million-exploit-400131).

On Ethereum: [Aave V3 Pool](https://etherscan.io/address/0x87870Bca3F3fD6335C3F4ce8392D69350B4fA4E2), [rsETH](https://etherscan.io/address/0xa1290d69c65a6fe4df752f95823fae25cb99e5a7), [rsETH OFT adapter](https://etherscan.io/address/0x85d456b2dff1fd8245387c0bfb64dfb700e98ef3), [LayerZero EndpointV2](https://etherscan.io/address/0x1a44076050125825900e736c501f859c50fe728c).
