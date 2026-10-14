"""ClinVar conflicting classifications - project processing module.

Configures dsprep for this dataset: manual parsing fixes from eda_decisions.yml, stateless domain
features, and the two feature sets (catboost, gbm). The dsprep library itself is not modified.
"""
import numpy as np
import pandas as pd

import dsprep as dp

ORIGIN_BITS = {1: "germline", 2: "somatic", 4: "inherited", 8: "paternal", 16: "maternal", 32: "de_novo"}
TRANSITIONS = {("A", "G"), ("G", "A"), ("C", "T"), ("T", "C")}
GROUP_COL = "SYMBOL"


# ---------------------------------------------------------------- manual parsing fixes (EDA: fix=manual)
def first_number(s):
    """'943-944' -> 943, '?-117' -> 117, '552' -> 552, NaN stays NaN."""
    return pd.to_numeric(s.astype("string").str.extract(r"(\d+)")[0], errors="coerce").astype(float)


def parse_fields(df):
    """Positions stored as text -> number; 'n/total' strings -> number, total and relative position."""
    df = df.copy()
    for c in ["cDNA_position", "CDS_position", "Protein_position"]:
        if c in df:
            df[c] = first_number(df[c])
    for c in ["EXON", "INTRON"]:
        parts = df[c].astype("string").str.split("/", expand=True)
        df[f"{c}_num"] = first_number(parts[0])
        df[f"{c}_total"] = first_number(parts[1])
        df[f"{c}_frac"] = df[f"{c}_num"] / df[f"{c}_total"]
    return df.drop(columns=["EXON", "INTRON"])


# ---------------------------------------------------------------- stateless domain features
def add_domain_features(df):
    """Row-level features; safe before or after splitting (no fitted state, no target)."""
    df = df.copy()
    df[GROUP_COL] = df[GROUP_COL].fillna("__no_gene__")  # 16 MT variants have no gene annotation
    af = df[["AF_ESP", "AF_EXAC", "AF_TGP"]]
    for c in af:
        df[f"{c}_zero"] = (df[c] == 0).astype(int)
    df["AF_max"] = af.max(axis=1)
    df["AF_n_cohorts"] = (af > 0).sum(axis=1)

    for bit, name in ORIGIN_BITS.items():
        df[f"origin_{name}"] = (df["ORIGIN"] & bit > 0).astype(int)
    df["origin_n_bits"] = df["ORIGIN"].apply(lambda v: bin(int(v)).count("1"))

    df["ref_len"] = df["REF"].str.len()
    df["alt_len"] = df["ALT"].str.len()
    df["len_diff"] = df["alt_len"] - df["ref_len"]
    snv = (df["ref_len"] == 1) & (df["alt_len"] == 1)
    df["snv_change"] = np.where(snv, df["REF"] + ">" + df["ALT"], "non_snv")
    df["is_transition"] = [int((r, a) in TRANSITIONS) for r, a in zip(df["REF"], df["ALT"])]

    aa = df["Amino_acids"].astype("string").str.split("/", expand=True)
    df["aa_ref"] = aa[0]
    df["aa_alt"] = aa[1].fillna(aa[0])  # synonymous variants list one amino acid
    df["aa_to_stop"] = df["aa_alt"].eq("*").fillna(False).astype(int)
    ref_codon = df["Codons"].astype("string").str.split("/").str[0]
    # 1-3: position of the changed base in the codon (VEP writes it in upper case)
    df["codon_pos"] = [next((i + 1 for i, ch in enumerate(c) if ch.isupper()), np.nan) if isinstance(c, str) else np.nan
                       for c in ref_codon.astype(object)]

    # List columns reshaped so dsprep.ListProcessor sees one token type per column
    df["CLNVI_sources"] = df["CLNVI"].str.split("|").apply(
        lambda xs: "|".join(sorted({x.split(":")[0] for x in xs})) if isinstance(xs, list) else np.nan)
    df["MC_terms"] = df["MC"].str.split(",").apply(
        lambda xs: "|".join(x.split("|")[-1] for x in xs) if isinstance(xs, list) else np.nan)
    df["CLNSIGINCL_sig"] = df["CLNSIGINCL"].str.split("|").apply(
        lambda xs: "|".join(x.split(":")[-1] for x in xs) if isinstance(xs, list) else np.nan)

    # Gene size in ClinVar: known from ClinVar itself at scoring time, uses no target
    df["gene_n_variants"] = df.groupby(GROUP_COL, dropna=False)[GROUP_COL].transform("size").astype(float)
    return df


def prepare(df_clean):
    """Cleaned frame (after dp.apply_cleaning) -> frame ready for the feature processors."""
    return add_domain_features(parse_fields(df_clean))


# ---------------------------------------------------------------- specs
NUMERIC = [
    "AF_ESP", "AF_EXAC", "AF_TGP", "AF_ESP_zero", "AF_EXAC_zero", "AF_TGP_zero", "AF_max", "AF_n_cohorts",
    "CADD_PHRED", "LoFtool", "BLOSUM62", "STRAND", "cDNA_position",
    "EXON_num", "EXON_total", "EXON_frac", "INTRON_num", "INTRON_total", "INTRON_frac",
    "origin_germline", "origin_somatic", "origin_inherited", "origin_paternal", "origin_maternal",
    "origin_de_novo", "origin_n_bits", "ref_len", "alt_len", "len_diff", "is_transition",
    "aa_to_stop", "codon_pos", "gene_n_variants",
]
NUMERIC_SPEC = {c: None for c in NUMERIC}
NUMERIC_SPEC["CADD_PHRED"] = {"missing_indicator": True}
NUMERIC_SPEC["LoFtool"] = {"missing_indicator": True}

IMPACT_ORDER = ["MODIFIER", "LOW", "MODERATE", "HIGH"]
CATEGORICAL = ["CHROM", "CLNVC", "IMPACT", "SIFT", "PolyPhen", "BAM_EDIT", "snv_change", "aa_ref", "aa_alt"]
RARE_GROUPED = ["CHROM", "CLNVC", "PolyPhen"]  # EDA rare_level_grouping

LISTS = {
    "CLNDN": {"method": ["stats", "multihot"], "sep": "|", "top_k": 30},
    "CLNDISDB": {"method": ["stats"], "sep": "|"},
    "CLNVI": {"method": ["stats"], "sep": "|"},
    "CLNVI_sources": {"method": ["multihot"], "sep": "|", "top_k": 10},
    "MC_terms": {"method": ["stats", "multihot"], "sep": "|", "top_k": 20},
    "Consequence": {"method": ["stats", "multihot"], "sep": "&", "top_k": 20},
    "CLNSIGINCL_sig": {"method": ["stats", "multihot"], "sep": "|", "top_k": 10, "min_frac": 0.0005},
}


def build_feature_processor(feature_set: str, task: str = "binary", group_col=GROUP_COL) -> dp.FeatureProcessor:
    """Fresh, unfitted processor - also what the modeling step refits inside each CV fold.

    catboost: categoricals native (pass fp.cat_features() to CatBoost), NaN kept.
    gbm:      categoricals ordinal (IMPACT with its natural order), rare levels grouped, NaN kept.
    """
    if feature_set == "catboost":
        cat = dp.CategoricalProcessor(CATEGORICAL, method="native")
    elif feature_set == "gbm":
        spec = {c: ({"method": "ordinal", "group_rare": True} if c in RARE_GROUPED else "ordinal") for c in CATEGORICAL}
        spec["IMPACT"] = {"method": "ordinal", "order": IMPACT_ORDER}
        cat = dp.CategoricalProcessor(spec)
    else:
        raise ValueError(feature_set)
    steps = {"num": dp.NumericProcessor(NUMERIC_SPEC), "cat": cat, "list": dp.ListProcessor(LISTS)}
    return dp.FeatureProcessor(steps=steps, task=task, group_col=group_col)


if __name__ == "__main__":  # usage example
    # dec = dp.load_decisions("eda_decisions.yml")
    # df, clean_log = dp.apply_cleaning(df_raw, dec)
    # df = prepare(df)
    # splits = dp.make_split(df, how="group_stratified", sizes=(0.7, 0.15, 0.15), group_col="SYMBOL", stratify_col="CLASS")
    # fp = build_feature_processor("gbm")
    # X_train = fp.fit_transform(splits["train"], y_train); X_val = fp.transform(splits["val"])
    pass
