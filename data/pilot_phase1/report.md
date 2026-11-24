## 1. Cost per run (sequential, concurrency 1)

Σ steps = sum of ORFS per-step wall times (tool time); container = the whole docker run
(adds image start-up and make overhead). Nested sub-steps are counted once (ADR-011).

| run | status | Σ steps wall s | container wall s | synth | floorplan | place | cts | route | finish | other | peak MB |
|---|---|---|---|---|---|---|---|---|---|---|---|
| aes_nangate45_44136fa3_r0 | success | 294.7 | 302.8 | 37.1 | 12.6 | 27.1 | 5.9 | 197.7 | 14.3 | 0.1 | 921 |
| aes_nangate45_44136fa3_r1 | success | 298.7 | 307.1 | 36.0 | 13.3 | 27.9 | 6.4 | 200.4 | 14.7 | 0.1 | 925 |
| aes_nangate45_44136fa3_r2 | success | 297.9 | 306.2 | 37.4 | 13.5 | 27.9 | 6.4 | 198.5 | 14.1 | 0.1 | 924 |
| aes_nangate45_6987feba_r0 | failed | 37.3 | 39.1 | 36.7 | 0.5 | – | – | – | – | 0.1 | 138 |
| aes_nangate45_6987feba_r1 | failed | 36.8 | 38.5 | 36.1 | 0.6 | – | – | – | – | 0.1 | 138 |
| aes_nangate45_6987feba_r2 | failed | 37.5 | 39.4 | 36.9 | 0.5 | – | – | – | – | 0.1 | 138 |
| aes_nangate45_a524613b_r0 | failed | 38.0 | 39.8 | 37.4 | 0.6 | – | – | – | – | 0.1 | 138 |
| aes_nangate45_a524613b_r1 | failed | 38.1 | 40.0 | 37.5 | 0.5 | – | – | – | – | 0.1 | 138 |
| aes_nangate45_a524613b_r2 | failed | 37.7 | 39.5 | 37.1 | 0.6 | – | – | – | – | 0.1 | 138 |
| aes_sky130hd_44136fa3_r0 | success | 1571.9 | 1580.4 | 38.3 | 16.4 | 28.1 | 7.5 | 1466.1 | 15.2 | 0.1 | 2867 |
| gcd_nangate45_44136fa3_r0 | success | 33.4 | 40.7 | 0.8 | 3.5 | 2.7 | 5.4 | 18.5 | 2.4 | 0.2 | 557 |
| gcd_nangate45_44136fa3_r1 | success | 32.5 | 40.1 | 0.8 | 3.7 | 2.7 | 5.5 | 17.5 | 2.2 | 0.1 | 556 |
| gcd_nangate45_44136fa3_r2 | success | 31.9 | 39.4 | 0.8 | 3.3 | 2.6 | 5.3 | 17.8 | 2.2 | 0.1 | 557 |
| gcd_sky130hd_44136fa3_r0 | success | 30.3 | 38.2 | 1.7 | 1.6 | 3.1 | 2.6 | 18.7 | 2.4 | 0.3 | 450 |
| ibex_nangate45_44136fa3_r0 | success | 285.7 | 293.9 | 45.4 | 4.0 | 27.7 | 10.1 | 172.3 | 26.1 | 0.1 | 959 |
| jpeg_nangate45_44136fa3_r0 | success | 820.7 | 830.1 | 34.6 | 35.1 | 98.6 | 79.0 | 511.7 | 61.7 | 0.1 | 1856 |

## 2. Run-to-run noise (identical config, ≥2 successful repeats)

| design | config | n | stage | mean wall s | CV wall | mean peak MB | CV peak |
|---|---|---|---|---|---|---|---|
| aes_nangate45 | 44136fa3 | 3 | synth | 36.81 | 1.9% | 120 | 0.2% |
| aes_nangate45 | 44136fa3 | 3 | floorplan | 13.14 | 3.7% | 157 | 0.1% |
| aes_nangate45 | 44136fa3 | 3 | place | 27.63 | 1.8% | 395 | 0.6% |
| aes_nangate45 | 44136fa3 | 3 | cts | 6.23 | 4.6% | 306 | 2.5% |
| aes_nangate45 | 44136fa3 | 3 | route | 198.85 | 0.7% | 923 | 0.3% |
| aes_nangate45 | 44136fa3 | 3 | finish | 14.38 | 2.2% | 439 | 3.0% |
| aes_nangate45 | 44136fa3 | 3 | other | 0.08 | 0.0% | 76 | 0.5% |
| gcd_nangate45 | 44136fa3 | 3 | synth | 0.79 | 3.3% | 96 | 1.6% |
| gcd_nangate45 | 44136fa3 | 3 | floorplan | 3.51 | 5.9% | 128 | 1.3% |
| gcd_nangate45 | 44136fa3 | 3 | place | 2.65 | 2.4% | 247 | 0.3% |
| gcd_nangate45 | 44136fa3 | 3 | cts | 5.37 | 2.1% | 232 | 2.1% |
| gcd_nangate45 | 44136fa3 | 3 | route | 17.92 | 2.9% | 557 | 0.1% |
| gcd_nangate45 | 44136fa3 | 3 | finish | 2.23 | 4.8% | 169 | 0.7% |
| gcd_nangate45 | 44136fa3 | 3 | other | 0.12 | 60.9% | 76 | 0.4% |
