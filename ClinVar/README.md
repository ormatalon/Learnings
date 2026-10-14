# ClinVar conflicting classifications - EDA

## Problem
ClinVar collects clinical-significance interpretations of human genetic variants from many labs. When labs disagree, the variant is marked as *conflicting*. Goal: predict that from the variant's genomic and functional annotation, to prioritize variants for re-review. Target `CLASS` is binary (1 = conflicting). One row = one variant on GRCh37 with its VEP annotation for one transcript; key `CHROM, POS, REF, ALT`. No dates in the snapshot.

## Data
- Source: Kaggle `kevinarvai/clinvar-conflicting`, file `clinvar_conflicting.csv` (loaded via `kagglehub`), 65,188 rows x 46 columns, not pre-split.
- No data dictionary in the download; column meanings come from the ClinVar VCF header and the Ensembl VEP field definitions.
- Notebook rules: no `CLAUDE.md` in this repo; cells follow `../AGENT.md` (user's choice).

| Type | Columns |
|---|---|
| continuous | AF_ESP, AF_EXAC, AF_TGP, CADD_PHRED, CADD_RAW, LoFtool, cDNA_position, CDS_position, Protein_position, DISTANCE |
| categorical | CHROM, CLNVC, ORIGIN (bit mask), IMPACT, SIFT, PolyPhen, BAM_EDIT, Feature_type, BIOTYPE, MOTIF_NAME, HIGH_INF_POS |
| low-card numeric | SSR, STRAND, BLOSUM62, MOTIF_POS, MOTIF_SCORE_CHANGE |
| high-card categorical | REF, ALT, Allele, SYMBOL, Feature, EXON, INTRON, Amino_acids, Codons |
| list | CLNDISDB, CLNDISDBINCL, CLNDN, CLNDNINCL, CLNSIGINCL, CLNVI, MC, Consequence |
| identifier | POS, CLNHGVS |
| target | CLASS |

## Key findings
- **Quality:** no duplicates, no invalid values, no missing target. Key is unique. 3,911 rows share a position with another allele (targets agree 70%).
- **Target:** 25.2% conflicting (16,434 / 65,188), 3:1.
- **Missing values:** structural. SIFT / PolyPhen / BLOSUM62 (~62%) exist only for missense; codon / protein fields (15%) only for exonic variants; MT variants have no gene annotation. `CLNVI` missing (58%) is informative: 20% vs 32% conflicting.
- **Distributions:** allele frequencies are zero-inflated (37-58% zeros) with spikes at each cohort's detection floor; positions are skewed by giant genes (TTN, SYNE1, NEB). No outliers removed, all values plausible.
- **Categoricals:** 94% SNVs, 98% germline-only ORIGIN; ORIGIN is a bit mask, not a category. Rare levels in CLNVC, CHROM (MT), Consequence.
- **Redundancy:** CADD_RAW = CADD_PHRED (rank), cDNA = CDS = Protein position, Allele = ALT, Feature ~ SYMBOL, IMPACT = grouped Consequence.
- **Target relations:**
  - Allele frequency is the strongest signal and inverted-U shaped: 17% conflicting when absent from ExAC, up to 48% for rare observed variants, 2% for common ones.
  - HIGH impact (loss of function) 7% vs 27% for the rest.
  - The gene matters most: per-gene rate 13-42% (10th-90th pct), Cramer's V 0.24.
  - Simpson's paradox: AF and CADD reverse direction between HIGH / MODERATE and LOW / MODIFIER impact.

## Data quality actions
- Parsing (analysis frame only): position columns text -> first number of a range (2,276 / 2,201 / 1,206 range values); EXON / INTRON split into number and total.
- `-` in `Allele` is a deletion code, not a null; excluded from null tokens.
- Sentinel conversions: none. Outlier removals: none.

## Leakage and validation
- No feature has AUC above 0.58.
- Check with user: `CLNDN` / `CLNDISDB` (number of disease names reflects number of submitters; 22% -> 40% conflicting) and `CLNSIGINCL` (a significance field).
- Keep: `CLNVI`.
- Split: stratified on `CLASS` (99% of test variants fall in genes seen in training, like production), plus a StratifiedGroupKFold by `SYMBOL` check for unseen genes. Fit gene encodings inside folds.
- Metric: PR-AUC primary; ROC-AUC, Brier, F1 secondary. Report SNVs vs indels and by IMPACT.

## Modeling recommendations
- Drop: POS, CLNHGVS, Allele, Feature, Feature_type, BIOTYPE, MOTIF_* / HIGH_INF_POS, DISTANCE, SSR, CLNDISDBINCL, CLNDNINCL, CADD_RAW, CDS_position, Protein_position.
- Encode missing as "not applicable" for missense-only and exon-only fields; missing indicators for CLNVI, CADD_PHRED, LoFtool.
- AF: zero flags plus log10 for linear models; tree models preferred because of the non-monotonic shape and impact interactions.
- Manual treatment: REF / ALT (lengths, indel size), SYMBOL (encoded in folds), list fields (CLNDN, CLNDISDB, CLNVI, MC, Consequence), ORIGIN bits, EXON / INTRON, Amino_acids / Codons.
- Group rare levels: CLNVC (Indel, Insertion, Inversion, Microsatellite), CHROM MT, PolyPhen unknown, rare Consequence combinations.
- Class weights for the 3:1 imbalance.

## Figures
- [Target](figures/04_target.png)
- [Missing per column](figures/05_missing_per_column.png), [missing co-occurrence](figures/05_missing_cooccurrence.png)
- [Non-zero allele frequencies](figures/06_af_nonzero_log.png)
- [Numeric correlations](figures/09_numeric_correlations.png), [Cramer's V](figures/09_cramers_v.png)
- [Association ranking](figures/10_target_association_ranking.png), [rate by level](figures/10_target_rate_by_level.png), [binned rates](figures/10_binned_target_rate.png)
- [Simpson check](figures/10_simpson_cadd_by_impact.png), [rate per gene](figures/10_gene_target_rate.png)

## Handoff
`eda_decisions.yml` holds every decision above in machine-readable form for the data processing step. Open questions are listed at its end.
