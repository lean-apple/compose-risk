# KelpDAO → Aave, safe version

The same contracts as [`kelpdao-aave-2026`](../kelpdao-aave-2026), except that `layers/2-upstream/EndpointConfig.sol` requires two independent verifiers. One compromised verifier can no longer deliver a forged message, and `exploit/Exploit.t.sol` checks that the attack is rejected.
