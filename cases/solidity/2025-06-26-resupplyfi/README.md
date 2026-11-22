# ResupplyFi crvUSD/wstUSR market (June 2025)

- **LendingPair** lends a stablecoin against vault shares, with an exchange rate of 1e36 divided by the share price.
- **VaultOracle** prices a share at the assets it redeems for.
- **ShareVault** is an ERC4626-style vault whose virtual shares keep a donation from taking value from later depositors.

No layer shows the risk when read alone. The vault prices shares fairly, the oracle reports that price, and the pair's formula is exact for ordinary prices. Together, a donation to the empty vault leaves one wei of shares worth over 1e36 per whole share, the pair's exchange rate floors to zero, and the solvency check passes for any loan.

`vulnerable/` is the system as described, with an exploit that borrows the pair's whole balance against one wei of shares. `fixed/` changes only `VaultOracle.sol` to reject a share price of 1e22 or more, and the same attack is rejected.

## What happened

On June 26, 2025, about an hour and a half after Resupply deployed its crvUSD/wstUSR pair, an attacker donated about 2,000 crvUSD to the market behind its empty CurveLend vault, deposited about 2 crvUSD for one wei of shares, posted that wei as collateral and borrowed the pair's full 10,000,000 reUSD. The pair computed its exchange rate as 1e36 divided by the oracle's share price; with the price near 2e36, the rate rounded to zero and the solvency check passed. Resupply paused the pair about an hour later, and reported $10M of bad debt.

Resupply then added two checks: the pair reverts on a zero exchange rate, and the oracle rejects a share price of 1e22 or more.

Sources: [Resupply post-mortem](https://paragraph.com/@resupply/resupply-crvusd-wstusr-market-post-mortem), [Resupply code and fix](https://github.com/resupplyfi/resupply), [BlockSec analysis](https://blocksec.com/blog/in-depth-analysis-and-reflections-on-the-resupply-protocol-attack-incident) for the attack transaction.
