# ClinVar conflicting classifications - EDA

Notebook: [eda_clinvar.ipynb](eda_clinvar.ipynb). Figures: [figures/](figures/).

## Problem

ClinVar collects clinical-significance classifications of human genetic variants from many labs. When labs disagree, the variant has *conflicting interpretations*. The goal is to predict, from genomic and functional annotation, whether a variant will get conflicting classifications, so that variants can be prioritized for expert review. The target is `CLASS` (binary; 1 = conflicting). One row is one variant, keyed by `CHROM, POS, REF, ALT`. Variants repeat within genes (`SYMBOL`). There are no timestamps.

## Dataset

- Source: Kaggle `kevinarvai/clinvar-conflicting`, one file `clinvar_conflicting.csv`, 65,188 rows x 46 columns, no train/test split.
- No data dictionary ships with the download. Column meanings come from ClinVar VCF INFO fields and Ensembl VEP conventions.
- Target: 16,434 conflicting (25.2%) vs. 48,754 (74.8%).

| Type | Columns |
|---|---|
| Target | CLASS |
| Identifier | CLNHGVS, POS, Feature, CLNVI |
| Continuous | AF_ESP, AF_EXAC, AF_TGP, LoFtool, CADD_PHRED, CADD_RAW, cDNA_position, CDS_position, Protein_position, DISTANCE |
| Low-cardinality numeric | BLOSUM62, STRAND, SSR, MOTIF_POS, MOTIF_SCORE_CHANGE |
| Categorical | CHROM, CLNVC, ORIGIN, IMPACT, Feature_type, BIOTYPE, BAM_EDIT, SIFT, PolyPhen, MOTIF_NAME, HIGH_INF_POS |
| High-cardinality categorical | REF, ALT, Allele, SYMBOL, EXON, INTRON, Amino_acids, Codons, Consequence, MC, CLNSIGINCL |
| Free text | CLNDN, CLNDNINCL, CLNDISDB, CLNDISDBINCL |

## Key findings

- **Grain**: the key is unique, and there are no duplicates of any kind. There are 2,328 genes: median 7 variants per gene, TTN has 2,765 (4%), and the top 10 genes hold 20% of rows.
- **Invalid values**: none out of range. Allele frequencies are 0 in 37-58% of rows, most likely "not observed", which is kept as its own state. `Allele = '-'` means a deletion, not a null.
- **Target**: 2.97:1 imbalance. Use PR-AUC (baseline 0.25) plus ROC-AUC, not accuracy.
- **Missing values**: 9 columns are 99.7-100% empty. The rest is structural, explained by variant type (MAR, tree AUC 0.90-0.99): SIFT, PolyPhen and BLOSUM62 exist only for missense variants (61% missing), and protein fields only for coding variants (15%). Little's test rejects MCAR. `CLNVI` is plausibly MNAR (studied variants get IDs).
- **Distributions**: allele frequencies and positions have skew ~5.5 (log views provided). CADD_PHRED is multi-modal. No values were removed.
- **Categoricals**: `CLNVC` is 94% SNV and `ORIGIN` is 98% germline (representation risk for indels and somatic variants). `Feature_type` and `BIOTYPE` are constant. There are no spelling variants.
- **Redundancy**: CADD_RAW and CADD_PHRED have Spearman 1.0, the three position columns r = 1.0, and the three AF sources r = 0.81-0.85. SIFT, PolyPhen, IMPACT and CADD overlap (epsilon-squared up to 0.51).
- **Target relationships**:
  - **Allele frequency** is non-monotonic. The conflict rate is 15% at AF = 0, peaks at ~49% around AF 1e-3, and falls to 2% for common variants. The AUC is only 0.55, but the mutual information is the highest.
  - **Consequence**: frameshift, stop-gained and splice donor/acceptor variants conflict 6-9% of the time; UTR and splice-region variants 33-37%.
  - **Gene**: among genes with 20 or more variants, the conflict rate ranges 0.00-0.91 (Cramer's V 0.31).
  - **Weak features**: CADD, LoFtool, SIFT and PolyPhen are weak on their own.
- **Simpson check**: the AF effect reverses direction across IMPACT. The AUC is 0.64 for HIGH and 0.39 for MODIFIER, because the peak of the inverted U shifts. Interactions matter.

## Data quality actions

| Step | Detail | Rows |
|---|---|---|
| parse | cDNA_position: text to number (first coordinate of ranges) | 2,276 |
| parse | CDS_position: text to number | 2,201 |
| parse | Protein_position: text to number | 1,206 |
| parse | ORIGIN, CHROM cast to string (codes) | 0 |

- **Sentinel conversions**: none. The AF zeros are ambiguous and were kept.
- **Outliers removed**: none. The IQR/MAD flags are real extremes: common variants and long genes.

## Leakage and split

- **Drop for a new-variant model**: `CLNDN` and `CLNDISDB`. The number of listed conditions (AUC 0.57) is a proxy for the number of submissions, and a conflict needs at least two submissions. Also drop the `CLN*INCL` columns (empty).
- **Check with user**: `CLNVI` (AUC 0.58). It is ClinVar-derived, so its availability at prediction time depends on the use case.
- **Keep**: allele frequencies, VEP, CADD, SIFT, PolyPhen and LoFtool. No feature exceeds AUC 0.95.
- **Split**: there is no time column. A random split leaves 99.2% of test rows in genes seen in training, so use `StratifiedGroupKFold` on `SYMBOL`, stratified by `CLASS`. Keep a holdout of ~20% of genes, and report metrics per `IMPACT` and `CLNVC`.

## Modeling recommendations

- **Drop**: near-empty and constant columns, identifiers, `CADD_RAW`, two of the three position columns, and the ClinVar-derived text fields.
- **Transform**: `log10(AF + 1e-5)` (or raw AF for trees), `log1p` for positions. Group rare `ORIGIN`, `CLNVC` and `CHROM` levels.
- **Manual treatment**: `SYMBOL` (target encoding inside folds), `Consequence` and `MC` (multi-valued terms), `EXON` and `INTRON` (number/total), `REF`/`ALT` lengths, `Amino_acids`, `Codons`.
- **Model**: gradient-boosted trees, which handle the non-monotonic AF, the interactions and the structural NaNs. Metrics: PR-AUC and ROC-AUC with a per-group breakdown.

## Key figures

- [Target](figures/04_target.png)
- [Variants per gene](figures/01_rows_per_gene.png)
- [Missing values](figures/05_missing_bar.png), [co-occurrence](figures/05_missing_cooccurrence.png)
- [Numeric distributions](figures/06_numeric_distributions.png)
- [Categorical counts](figures/07_categorical_counts.png)
- [Numeric correlation](figures/09_numeric_correlation.png), [Cramer's V](figures/09_cramers_v.png)
- [Target association ranking](figures/10_target_association_rank.png)
- [Conflict rate by numeric bins](figures/10_numeric_binned_rate.png), [by category](figures/10_categorical_rate.png)
- [Simpson check: AF within IMPACT](figures/10_simpson_check.png)
