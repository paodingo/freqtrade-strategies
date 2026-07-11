# Stage 3C.1 Research Data Plane

- Campaign: `stage3c1-research-data-plane`
- Complete: `true`
- Strategy modified: `false`
- Candidate created: `false`
- Hyperopt run: `false`
- Holdout accessed: `false`
- Quality evaluation performed: `false`

## Split

- Split manifest: `research/data/splits/futures-dev-validation-v1.yaml`
- Development dataset: `futures-dev-btc-usdt-usdt-20260301-20260328-v1`
- Development aggregate: `5435e5573743354059c65c3ef15e509c18b0e486016d81071c54f86f6caa78c9`
- Validation dataset: `futures-validation-btc-usdt-usdt-20260503-20260628-v1`
- Validation aggregate: `21ffdeffee3ae17a88a3d455ae4fe1e1970823c7e0c123842964d427adccac22`
- Acceptance fixture timerange `20260329-20260412` is inside embargo and is not used for ranking.

## Governance

- Usage policy: `research/data/data-usage-policy.yaml`
- Validation access policy: `research/data/validation-access-policy.yaml`
- Pollution model: `research/data/pollution-state-model.yaml`
- Evaluation schema reserved for Stage 3C.2: `research/data/evaluation-result.schema.json`
- Lineage database: `research/data/data-lineage.sqlite`

## Readiness Probes

- Purpose: `data_readiness_only`
- Quality verdict: `not_evaluated`
- Development probe status: `accepted`
- Validation probe status: `accepted`

These probes only verify that the sealed data can be consumed by the offline runner. They do not rank or approve strategy quality.
