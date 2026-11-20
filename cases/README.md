# Cases

Each case is a small system of contracts rebuilt from a real incident. `layers/` holds one folder per contract, numbered by distance from the protocol under review (`0-target`); `exploit/` holds a Foundry test that runs the attack; `case.json` holds the expected verdict, the layer of the root cause and the threat model the review is judged under.

A risky case has a safe counterpart that differs in one file and must be judged safe. Both share the same threat model.
