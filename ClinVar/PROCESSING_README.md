# ClinVar - data processing

Turns `eda_decisions.yml` into training-ready matrices. Notebook: `processing_clinvar.ipynb`. Project module: `processing_clinvar.py`. Library: `dsprep/` (copied from the data-processing skill, unmodified).

## Recommended vs. done
| Decision | EDA recommendation | Done (user choice) |
|---|---|---|
| CLNDN, CLNDISDB | check with user (submitter-count proxy) | kept |
| CLNSIGINCL | check with user, default drop | kept (risk: it is a clinical-significance field) |
| Split | stratified on CLASS | group-stratified by SYMBOL (unseen genes) |
| Feature sets | - | catboost + gbm |
| Class weights | recommended | computed and recorded, not applied |

## What was done
- **Cleaning:** 17 recommended columns dropped. No rows removed (no duplicates or invalid values).
- **Parsing:** positions take the first number of a range; EXON / INTRON become `_num`, `_total`, `_frac`.
- **Engineered features (stateless):**
  - AF zero flags, max AF, number of cohorts observed
  - ORIGIN bit flags
  - REF/ALT lengths, SNV substitution, transition flag
  - amino-acid pair, stop gain, codon position
  - list columns reshaped (CLNVI database sources, MC term names, CLNSIGINCL labels)
  - `gene_n_variants`: ClinVar variants per gene, computed on the full frame with no target
- **Split:** group-stratified by gene. Actual shares are 74.1 / 14.0 / 12.0% (48,279 / 9,107 / 7,802 rows), off the 70/15/15 request because genes are large (BRCA2 is 21% of val). Positives: 25.2 / 26.0 / 24.5%. No gene is shared between splits.
- **Target:** binary, positive = 1, no transform. Balanced weights {0: 0.668, 1: 1.987}.
- **Not a feature:** `SYMBOL` is the split group. Under a gene-grouped split, test genes are unseen, so a gene encoding would not transfer.

## Feature sets (126 columns each)
- 35 numeric, 9 categorical, 82 list-derived (CLNDN top 30 diseases, Consequence / MC flags, CLNVI sources, counts).
- `catboost`: categoricals kept as strings; NaN kept.
- `gbm`: categoricals ordinal (IMPACT ordered MODIFIER < LOW < MODERATE < HIGH), rare levels grouped; NaN kept.

## Screening and validation
- **Leakage scan:** no suspect (max single-feature AUC 0.58).
- **Safe-to-drop recommendation (not applied, needs your approval):**
  - constant: `CLNDN__missing`, `CLNDISDB__missing`, `Consequence__missing`
  - duplicate: `CLNDISDB__len`, `MC_terms__n_unique`, `Consequence__n_unique`
- **Drift train vs test:** 9 features with major PSI, all gene-level (`gene_n_variants`, exon/intron totals, LoFtool, CHROM, gene-specific disease flags). This is expected from the gene-grouped split.
- **Baseline on val:**

  | model | ROC-AUC | PR-AUC |
  |---|---|---|
  | dummy | 0.500 | 0.260 |
  | HistGradientBoosting | 0.834 | 0.633 |

## Outputs
- `data/processed/X_{train,val,test}_{catboost,gbm}.parquet`, `y_{split}.parquet`, `groups_{split}.parquet`
- `models/feature_processor_{catboost,gbm}.joblib`, `models/target_processor.joblib`
- `feature_dictionary_{catboost,gbm}.csv`, `processing_record.yml`

```python
import pandas as pd
d = "data/processed"
X_tr = pd.read_parquet(f"{d}/X_train_catboost.parquet"); y_tr = pd.read_parquet(f"{d}/y_train.parquet")["CLASS"]
X_va = pd.read_parquet(f"{d}/X_val_catboost.parquet");   y_va = pd.read_parquet(f"{d}/y_val.parquet")["CLASS"]
cat_features = ["CHROM", "CLNVC", "IMPACT", "SIFT", "PolyPhen", "BAM_EDIT", "snv_change", "aa_ref", "aa_alt"]
# CatBoostClassifier(cat_features=cat_features).fit(X_tr, y_tr, eval_set=(X_va, y_va))
```

## Handoff to modeling
- The saved matrices are fitted on the whole train split. Use them for a final model and for scoring val/test.
- For cross-validation, refit inside each fold: `processing_clinvar.build_feature_processor("gbm" | "catboost")` returns a fresh processor.
- Build folds that match the split with `dsprep.make_cv_folds(train, how="group_stratified", group_col="SYMBOL", stratify_col="CLASS")`.
- With one gene able to dominate val or test, prefer CV scores over a single val score.
