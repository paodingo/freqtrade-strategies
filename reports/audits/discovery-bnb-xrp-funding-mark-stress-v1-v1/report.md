# BNB/XRP Funding and Mark Stress Profile

- Classification: `no_persistent_additional_pair_joint_stress`
- Persistent slices: `1/4`
- Absolute funding threshold: `0.000432684`
- Absolute mark-return threshold: `0.0368000093753`

## Full-window joint stress

| Asset | Funding stress | Mark stress | Joint stress | Joint lift | Longest run |
|---|---:|---:|---:|---:|---:|
| BTC | 5.280% | 4.480% | 0.320% | 1.353 | 1 |
| ETH | 4.800% | 5.600% | 0.160% | 0.595 | 1 |
| BNB | 12.960% | 6.400% | 0.800% | 0.965 | 2 |
| XRP | 8.320% | 6.400% | 1.280% | 2.404 | 2 |

## Frozen-slice decision

| Slice | BTC | ETH | BNB | XRP | Both additional pairs exceed baseline max |
|---|---:|---:|---:|---:|---|
| ranging-short-ablation-s01 | 1.274% | 0.637% | 1.911% | 5.096% | yes |
| ranging-short-ablation-s02 | 0.000% | 0.000% | 1.282% | 0.000% | no |
| ranging-short-ablation-s03 | 0.000% | 0.000% | 0.000% | 0.000% | no |
| ranging-short-ablation-s04 | 0.000% | 0.000% | 0.000% | 0.000% | no |

## Governance conclusion

This is Development-only descriptive evidence. It does not authorize a backtest, Candidate, strategy change, Validation/Holdout access, promotion, or trading.
