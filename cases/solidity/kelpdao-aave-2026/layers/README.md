# Layers

One folder per contract, numbered by distance from the pool under review: `0-target` is the pool, `1-upstream` the token it accepts, `2-upstream` the endpoint the token trusts. A layer only imports from higher numbers.
