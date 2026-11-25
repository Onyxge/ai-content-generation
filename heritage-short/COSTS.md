# COSTS

Generated from `runs.jsonl` and `stages.jsonl` by `film costs` (unit U9, not built yet). It will hold:
- calls, median and p95 latency, and GPU minutes per stage;
- the free-tier limits we actually hit, read from the providers' error bodies;
- a list-price equivalent, with each price's source and date.

We have no frontier-model access (compute is Kaggle T4s and Colab), so there will be no frontier comparison; the brief asks for one only where we had access.

Measured so far, on mock providers only (this says nothing about model costs):

| Run | What ran | Wall time |
|---|---|---|
| Full-size mock build, 25 Nov | 31 placeholder "model" units, 16 Ken Burns renders at 720p, four 67 s exports | 87 s on the build sandbox |
