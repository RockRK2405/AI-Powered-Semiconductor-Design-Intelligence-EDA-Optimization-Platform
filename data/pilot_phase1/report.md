## 1. Cost per run (sequential, concurrency 1)

| run | status | total wall s | synth | floorplan | place | cts | route | finish | other | peak MB |
|---|---|---|---|---|---|---|---|---|---|---|
| aes_nangate45_44136fa3_r0 | success | 297.5 | 37.1 | 12.6 | 27.1 | 7.2 | 197.7 | 15.8 | 0.1 | 921 |
| aes_nangate45_44136fa3_r1 | success | 301.8 | 36.0 | 13.3 | 27.9 | 7.8 | 200.4 | 16.4 | 0.1 | 925 |
| aes_nangate45_44136fa3_r2 | success | 301.0 | 37.4 | 13.5 | 27.9 | 7.9 | 198.5 | 15.7 | 0.1 | 924 |
| aes_nangate45_6987feba_r0 | failed | 37.3 | 36.7 | 0.5 | – | – | – | – | 0.1 | 138 |
| aes_nangate45_6987feba_r1 | failed | 36.8 | 36.1 | 0.6 | – | – | – | – | 0.1 | 138 |
| aes_nangate45_6987feba_r2 | failed | 37.5 | 36.9 | 0.5 | – | – | – | – | 0.1 | 138 |
| aes_nangate45_a524613b_r0 | failed | 38.0 | 37.4 | 0.6 | – | – | – | – | 0.1 | 138 |
| aes_nangate45_a524613b_r1 | failed | 38.1 | 37.5 | 0.5 | – | – | – | – | 0.1 | 138 |
| aes_nangate45_a524613b_r2 | failed | 37.7 | 37.1 | 0.6 | – | – | – | – | 0.1 | 138 |
| aes_sky130hd_44136fa3_r0 | success | 1576.3 | 38.3 | 16.4 | 28.1 | 9.2 | 1466.1 | 17.9 | 0.1 | 2867 |
| gcd_nangate45_44136fa3_r0 | success | 34.0 | 0.8 | 3.5 | 2.7 | 5.7 | 18.5 | 2.6 | 0.2 | 557 |
| gcd_nangate45_44136fa3_r1 | success | 33.0 | 0.8 | 3.7 | 2.7 | 5.7 | 17.5 | 2.4 | 0.1 | 556 |
| gcd_nangate45_44136fa3_r2 | success | 32.4 | 0.8 | 3.3 | 2.6 | 5.5 | 17.8 | 2.4 | 0.1 | 557 |
| gcd_sky130hd_44136fa3_r0 | success | 31.2 | 1.7 | 1.6 | 3.1 | 3.0 | 18.7 | 2.9 | 0.3 | 450 |
| ibex_nangate45_44136fa3_r0 | success | 300.0 | 45.4 | 4.0 | 27.7 | 11.6 | 172.3 | 38.9 | 0.1 | 959 |
| jpeg_nangate45_44136fa3_r0 | success | 860.0 | 34.6 | 35.1 | 98.6 | 93.5 | 511.7 | 86.5 | 0.1 | 1856 |

## 2. Run-to-run noise (identical config, ≥2 successful repeats)

| design | config | n | stage | mean wall s | CV wall | mean peak MB | CV peak |
|---|---|---|---|---|---|---|---|
| aes_nangate45 | 44136fa3 | 3 | synth | 36.81 | 1.9% | 120 | 0.2% |
| aes_nangate45 | 44136fa3 | 3 | floorplan | 13.14 | 3.7% | 157 | 0.1% |
| aes_nangate45 | 44136fa3 | 3 | place | 27.63 | 1.8% | 395 | 0.6% |
| aes_nangate45 | 44136fa3 | 3 | cts | 7.63 | 4.7% | 306 | 2.5% |
| aes_nangate45 | 44136fa3 | 3 | route | 198.85 | 0.7% | 923 | 0.3% |
| aes_nangate45 | 44136fa3 | 3 | finish | 15.97 | 2.5% | 439 | 3.0% |
| aes_nangate45 | 44136fa3 | 3 | other | 0.08 | 0.0% | 76 | 0.5% |
| gcd_nangate45 | 44136fa3 | 3 | synth | 0.79 | 3.3% | 96 | 1.6% |
| gcd_nangate45 | 44136fa3 | 3 | floorplan | 3.51 | 5.9% | 128 | 1.3% |
| gcd_nangate45 | 44136fa3 | 3 | place | 2.65 | 2.4% | 247 | 0.3% |
| gcd_nangate45 | 44136fa3 | 3 | cts | 5.64 | 2.0% | 232 | 2.1% |
| gcd_nangate45 | 44136fa3 | 3 | route | 17.92 | 2.9% | 557 | 0.1% |
| gcd_nangate45 | 44136fa3 | 3 | finish | 2.49 | 4.8% | 169 | 0.7% |
| gcd_nangate45 | 44136fa3 | 3 | other | 0.12 | 60.9% | 76 | 0.4% |
