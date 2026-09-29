---
name: eda
description: Structured EDA of a tabular dataset before modeling; outputs an executed Jupyter notebook and a README. Use when asked to explore, profile, or check the quality of a dataset.
---

# Exploratory Data Analysis (EDA)

Use this skill when the user asks for an EDA, wants to explore, profile or understand a tabular dataset, check its quality, or prepare it for a predictive model. Do not use it for a single ad-hoc chart or for a quick question about one column.

The goal is an EDA that reads like the work of a senior data scientist: every check has a reason, every plot has an interpretation, and every finding ends in an implication for modeling. Deliver two files: an executed Jupyter notebook and a README.

## Step 0 - Preconditions (before writing any analysis)

### 0.1 Notebook code rules
Look for the project's notebook coding rules in this order: `CLAUDE.md`, `.claude/CLAUDE.md`, then any `*.md` under `.claude/` excluding `.claude/skills/` (skill files are not coding rules).
- If found, read it fully. Every code cell must follow it. It overrides any style suggestion in this skill, except that figures are always saved (see Step 4).
- If not found, stop and tell the user: "I couldn't find the notebook code rules file (`CLAUDE.md` or `.claude/`). Please add it so the notebook follows your conventions." Continue only if the user explicitly says to proceed without it, and note that in the README.

### 0.2 Dataset description
Look for a file that explains the dataset: `README*`, `*data_dictionary*`, `*codebook*`, `*description*`, `*metadata*`, a `docs/` folder, or text/PDF files next to the data. If found, treat it as the source of truth for the problem, target, row meaning, feature definitions, units and special codes (for example "-1 = unknown"). If not found, infer from column names and values, and state which parts are inferred.

### 0.3 Data files and splits
Identify all data files and check whether the data is already split (`train`/`test`/`val`, `holdout`, date-suffixed files). Record shapes and whether the test set contains the target.
- If split: run every analysis in Sections 1-11 on the **train set only**. Use the test set only in Section 12. Looking at test data while exploring leaks information into modeling decisions.
- If not split: analyze the full data, and give split recommendations in Section 12.

## Step 1 - Problem understanding (first markdown cell)

Write one clear paragraph covering:
- **Subject and product concept**: the domain, and the product or decision this data serves.
- **Goal**: what we want to predict or achieve, and how the prediction will be used.
- **Target**: column name, type (binary, multiclass, continuous, count, time-to-event) and meaning.
- **Unit of observation**: what one row represents (a customer, a transaction, a customer-month) and which columns form the key.
- **Timeline**, when relevant: when features are known versus when the target is realized.

If the target or the row meaning is ambiguous, ask the user before continuing.

## Working principles (apply throughout)

- **Keep the raw data untouched.** Load it as `df_raw`. Build `df` as the analysis frame and record every change (dropped duplicates, sentinel values converted to missing, fixed spellings, removed outliers) in a cleaning log table. The log goes into the README.
- **What to remove before analysis**: exact duplicates and confirmed invalid values (set the value to missing, don't drop the row). **What not to remove**: rows with missing values; compute statistics pairwise on available values and report the n used. Missingness is a finding in itself, and production data will contain it too.
- **Statistics**: report an effect size next to every p-value (large samples make everything "significant"), and apply Benjamini-Hochberg correction whenever many tests are run.
- **Choosing a measure**: when several measures could answer a question, pick the most suitable one, show it, and explain the choice in one sentence. Don't dump every measure.
- **Repeated rows per entity**: if Section 1 shows several rows per entity, the rows are not independent. P-values will look stronger than they are, and entities with many rows will dominate the statistics. Aggregate to entity level for tests, or state the caveat next to the results.
- **Outliers in plots**: extreme values can squash a plot so the bulk of the data is unreadable. For each plot, decide whether to show it with or without outliers. When the extremes compress the axis (for example, the maximum is far beyond the 99th percentile), exclude them from that plot only, typically by clipping the view to the 1st-99th percentile or the IQR fences, and state in the title or caption how many points are hidden. When the outliers themselves are the point, show them. This is temporary: statistics are always computed on the full data, and permanent removal follows the rules in Section 6.
- **Plots**: for large data, sample for plotting with a fixed random seed and state the sample size; compute statistics on the full data where feasible.
- **Section format**: a short markdown intro (what and why), the code, then a markdown **Findings** cell with concrete numbers and the implication for modeling. Never leave a plot without an interpretation.

## Step 2 - Analysis sections

### 1. First look
- Shape, memory use, `head()`, column data types.
- Fix parsing: numbers stored as text, thousand separators, units inside values, date strings. Log each fix.
- Classify every column into one of: continuous numeric, low-cardinality numeric (< 20 distinct values), categorical, high-cardinality categorical, free text, datetime, identifier, target. Show this as a table; later sections use it.
- **Rows with a missing target**: count them first. Exclude them from all target-related analysis. Ask the user what they are (unlabeled production data to score, or data errors) if it isn't obvious.
- **Grain check**: verify that the key from Step 1 is unique. If an entity (customer, patient, device) appears in several rows, report the distribution of rows per entity.
- **High-cardinality categoricals and free text**: list them with cardinality and example values, and note them as candidates for manual treatment. Don't engineer or encode them; the user handles them manually.

### 2. Duplicates
- Full-row duplicates: count, % of rows, examples.
- Duplicated key: separate exact duplicates from conflicting ones (same key, different values, especially a different target).
- Decide the handling (drop, keep first, aggregate) and state the reason. If it's unclear whether duplicates are legitimate repeated events, ask the user.

### 3. Suspicious and invalid values
Check each column, guided by the dataset description:
- Impossible ranges (negative ages or prices, percentages over 100, future dates, end before start).
- Spikes at round or boundary values (999, 9999, 1900-01-01, max int).
- Constant or near-constant columns.
- Whitespace, casing and encoding artifacts in strings.

Output a table: column | issue | count | % | example | action.

### 4. Target
Run this before the missingness and relationship sections, since they depend on understanding the target. This section describes the target on its own; its relationships with features are in Section 10.
- Categorical: class counts and %, imbalance ratio, bar plot. State implications (stratified splits, metrics like PR-AUC or F1 instead of accuracy, class weights).
- Numeric: histogram, boxplot, skewness, QQ plot, log view if right-skewed, zero-inflation check. State implications (target transform, loss choice, robust metrics).
- If there is a time column: plot the target over time to show drift or seasonality.

### 5. Missing values
- **Normalize disguised nulls first**: treat `"NA"`, `"N/A"`, `"null"`, `"None"`, `""`, `" "`, `"?"`, `"-"` as missing. Treat numeric sentinels (`0`, `-1`, `999`, `9999`) as missing only when the documentation or domain says they mean "unknown" (for example age = 0). List every conversion.
- Missing count and % per column (table and sorted bar chart), plus a co-occurrence heatmap showing columns that go missing together.
- **Mechanism**:
  - MCAR: Little's MCAR test (implement it if no maintained package is available), or compare other columns' distributions between missing and non-missing rows.
  - MAR: predict the missingness indicator from the other observed columns (logistic regression or a shallow tree) and report the AUC. An AUC well above 0.5 means missingness depends on observed data.
  - MNAR: can't be proven from the data; argue it from domain logic (for example, high earners skipping an income question) and flag suspected cases.
- **Missingness vs. target**: compare the target between missing and non-missing rows. If the difference is meaningful, recommend a missing-indicator feature.

### 6. Numeric distributions
For each continuous numeric column:
- Histogram with KDE, boxplot, and summary statistics (mean, median, std, skew, percentiles 1/5/25/50/75/95/99, min, max). Apply the outliers-in-plots rule from the working principles.
- **Shape**: judge normality visually with a QQ plot and the skewness value. Do not rely on normality tests; on large samples they reject for trivial deviations. If clearly skewed (roughly |skew| > 1), add a log-scale view (`log1p`, or symlog when negatives exist) side by side.
- **Outliers**: detect with IQR (1.5x) and robust z-score (MAD, |z| > 3.5). Report counts and examples.
- **Permanent removal - be careful**: remove only values that are clearly errors (impossible, physically implausible, data-entry mistakes). Keep genuine extremes; suggest a transform or capping instead. If you're not sure whether a value is an error or a real extreme, ask the user before removing it. Record each removal in an outlier table: column | method | threshold | n flagged | n removed | reason.

### 7. Categorical and low-cardinality numeric columns (each column on its own)
This section describes each column by itself. Relationships with other columns are in Section 9, and with the target (including the ANOVA-like test across levels) in Section 10.
- **Spelling consistency first**: normalize case, whitespace and punctuation, then fuzzy-match levels (for example `rapidfuzz`, ratio >= 90) to find variants such as "Tel Aviv" / "tel-aviv" / "TLV". Show the proposed mapping before merging.
- Count bar plot per column, sorted, with % labels.
- **Rare levels**: highlight levels under 1% of rows or under 30 observations; suggest grouping them into "Other".
- **Dominant levels**: flag columns where one level covers 90% or more of the rows (for example 90% male). Note the representation risk: the model will learn little about the minority, and results may not generalize to populations with a different mix.

### 8. Date and time columns
- Range, granularity and gaps (missing days or months), number of rows per period.
- Seasonality and trends in volume; features whose distribution shifts over time.
- Parse errors and impossible dates (already logged in Sections 1 and 3).
- Note which date parts could become features (day of week, month, time since an event), without engineering them.

### 9. Feature-feature relationships (target excluded)
- Numeric vs. numeric: Pearson and Spearman heatmaps side by side, annotated, lower triangle, diverging palette centered at 0. Flag pairs with |r| > 0.8 and pairs where Pearson and Spearman differ a lot (non-linear or outlier-driven).
- Categorical vs. numeric: Mann-Whitney U for two levels, with rank-biserial effect size. For more than two levels, Kruskal-Wallis first, then pairwise Mann-Whitney.
- Categorical vs. categorical: Cramer's V heatmap.
- Summarize redundant columns and candidates to drop or combine.

### 10. Feature-target relationships
- **Numeric features** - choose the most suitable association measure and explain the choice in one sentence:
  - Pearson when the relationship looks linear and there are no heavy outliers.
  - Spearman when it is monotonic but skewed or outlier-driven.
  - **Mutual information** when binned-mean or scatter plots show a non-monotonic shape (for example U-shaped), which correlation coefficients miss.
  - Binary target: single-feature AUC or Mann-Whitney with rank-biserial.
- **Categorical features - ANOVA-like test across levels**: test whether the target differs between the levels of each categorical variable.
  - Numeric target: Kruskal-Wallis with epsilon-squared effect size. If significant, run Dunn's post-hoc test (for example `scikit-posthocs`, BH-corrected) to show which levels differ from each other.
  - Categorical target: chi-square of independence with Cramer's V, plus the target rate per level with confidence intervals to show which levels stand out.
- Show a ranked table and bar chart of the chosen measures.
- Plots: boxplots or violins of the target by level for categoricals (target rate with confidence intervals for a categorical target); binned-mean or hexbin plots for the top numeric features.
- **Simpson's paradox**: for the top features, re-check the relationship within groups of key categorical variables (segment, region, time period). Flag any case where the direction or strength changes compared with the pooled data, and show the stratified plot.

### 11. Leakage verdict
Collect every leakage suspect from the earlier sections into one place:
- Features that are proxies of the target, or have a suspiciously strong single-feature association (for example AUC > 0.95).
- Features that are only known after the target is realized, or aggregates computed over the full time period.
- Conflicting duplicates found in Section 2.

Give a short verdict per suspect: keep, drop, or check with the user.

### 12. Train/test representativeness, or split recommendations

**If the data is already split**, check that the test set represents production:
- Distribution similarity per feature: KS test (numeric) or chi-square (categorical), plus PSI (flag > 0.1 moderate, > 0.25 major). Overlay plots for the most shifted features. Compare target distributions if the test set has labels.
- Adversarial validation: train a classifier to tell train rows from test rows. An AUC near 0.5 is good; report the features that drive any difference.
- Time: are test timestamps strictly after train?
- Entity overlap: the same customer, patient or device in both sets, and duplicates across the sets.
- Group representation: compare key group proportions between sets; flag over- or under-represented groups and levels that appear only in test.
- Production fit: does the test set look like what the model will see at inference (time period, population, features available at prediction time, label delay)? State the risks.

**If the data is not split**, give concrete recommendations based on the findings, for example:
- Split by time when there is a time column and the model will predict the future.
- Group split (for example GroupKFold) when entities repeat across rows.
- Stratify by the target when classes are imbalanced, and by key groups when some are small.
- Keep an out-of-time holdout that mimics production.

## Step 3 - Summary cell
End the notebook with a summary: the most important findings, the cleaning log, and the recommended next steps for modeling.

## Step 4 - Outputs

### Jupyter notebook
- Name it `eda_<dataset>.ipynb` and place it in the project's notebook folder (or next to the data).
- Follow the `.claude` notebook rules strictly; put reusable logic in functions.
- Save every figure to `figures/` with a descriptive name, even if the rules file says otherwise, so the README can link to them.
- Execute the notebook end to end (for example `jupyter nbconvert --to notebook --execute --inplace`) and fix all errors, so that outputs and plots are stored in the file.

### README
Write `README.md`, or `EDA_README.md` if a README already exists (never overwrite the user's file). Include:
1. The problem statement paragraph from Step 1.
2. Dataset overview: files, shapes, row meaning, key, target, time range, column-type table.
3. Key findings per section, as short bullets with numbers.
4. Data quality actions: the cleaning log, sentinel conversions and outlier removals.
5. Leakage verdict, and the train/test representativeness result or split recommendations.
6. Modeling recommendations: preprocessing, transforms, columns to drop, columns noted for manual treatment, validation scheme, metric.
7. Links to the key figures in `figures/`.

Finish by telling the user where both files are and the 3-5 most important findings, in one short message.
