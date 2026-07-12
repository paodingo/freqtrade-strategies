# Protected Manifest Checkout Hash Drift

- Classification: `checkout_eol_only`
- Semantic change: `false`
- Canonical scheme: `canonical_utf8_lf_v1`

| Path | old raw | worktree raw | canonical | semantic | aggregate | EOL |
|---|---|---|---|---|---|---|
| `research/data/snapshots/futures-dev-btc-usdt-usdt-20240101-20240830-v2/manifest.yaml` | `8f25623b43fd940a1d0ca989fecb9fdcb0319954937b484e3037a42525aa56ae` | `e60ecbb9c28be5910bf1d33c6ed03bf46798228a343670b71a738b4b9150cc13` | `e60ecbb9c28be5910bf1d33c6ed03bf46798228a343670b71a738b4b9150cc13` | `f06e0e2481f71ae683eba4f128b596ba299e264f8d640fc5a83856bb3fc60437` | `3e86474ba634c3779389d818997d1626357090da7fef6b9f007ad0f9bbcfdd5c` | `lf` |
| `research/data/snapshots/futures-dev-eth-usdt-usdt-20240101-20240830-v1/manifest.yaml` | `9eb0c84aed57d1468c476cd4fe753f9d3093016e08632a62ae1ae88c45899b88` | `6557a265a1d2904452a236a84e1afeb9db4508e0ec6952a134ca494d2433b925` | `6557a265a1d2904452a236a84e1afeb9db4508e0ec6952a134ca494d2433b925` | `4a5f0c3ba094089577312270d17863fcc1309a20146fcc584bf13ba4fa3850da` | `00ddc63806215087904425ae59543e62cac5d5aa2c8c29406b7f90eeb0c28187` | `lf` |
| `research/exchange_snapshots/binance-usdm-futures-2025-8-demo/manifest.yaml` | `8366ed573c51877c2c33aceca102084198b5d5780ef2de8fdf8bd75c6e017742` | `4c1ae6cdb1964fb5b1443f09df984536ecce5eb21357977d094b64406a191b52` | `4c1ae6cdb1964fb5b1443f09df984536ecce5eb21357977d094b64406a191b52` | `1ede7615d6823f0e1b8f9bb25a4263a50a00110abe3aefa737f6722c62f08b24` | `599d67345bed5b2b3b42669baf460fa336ffde80502cfd1880ea57cd0dc5074d` | `lf` |

All three Git blobs and current worktree files are UTF-8 without BOM, use LF, end with a newline, and are semantically identical to the previously approved CRLF checkout bytes. No Manifest business field or aggregate hash changed.
