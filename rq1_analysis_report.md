# RQ1: Comprehensive Analysis Report

## Methodology

To rigorously answer RQ1, we designed a multi-phase data extraction and validation pipeline against the `hao-li/AIDev` HuggingFace dataset.

### 1. Data Sources and Table Mappings

We cross-referenced three primary tables from the dataset:

- **`pull_request`**: We extracted `pr_id`, `pr_number`, `repo_id`, `created_at`, `merged_at`, and `agent_type`. This provided the foundational PR cohort and resolution timeframes.

- **`pr_commit_details`**: We mapped `pr_id` to aggregate every file modified in the PR. We utilized the `additions`, `deletions`, and `filename` columns to calculate exact code churn, isolating `test_loc` (testing lines of code) from `prod_loc` (production lines of code).

- **`repository`**: We mapped `repo_id` to extract both `stars` and `forks`, mathematically establishing the influence of project popularity.


### 2. Heuristic Test Classification

We initially isolated 'Test PRs' by parsing the `filename` of every changed file through exact heuristic regex rules:

- **Test Identification**: Files matching our proprietary regex targets: `(?:^|[\\/])(?:tests?|testing|cypress)(?:[\\/]?$|/)` (Directory Names), `(?:^|[\\/_.-])(?:test|spec)(?:[\\/_.-]?$)` (Filename Tokens), or `(?:Test|Spec)(?:$|\.)` (Suffixes) and not possessing an excluded extension (like `.md` or `.json`) were flagged as test files.

- **Type Classification**: We mapped test files to testing levels using path-based substring boundaries. Paths containing `e2e`, `cypress`, `playwright`, or `selenium` were binned as **E2E**. Paths containing `integration`, `api`, or `db` were binned as **Integration**. All remaining test paths defaulted to **Unit**.


### 3. GitHub GraphQL Augmentation

Because the static dataset lacked chronological pipeline execution states, we utilized the **GitHub GraphQL API** to natively reconstruct the timeline of each PR:

- **Chronological Commits**: We fetched exactly how many commits the agent submitted (`trial_and_error_commits`).

- **CI Pipeline Statuses**: We queried the `statusCheckRollup` for every commit SHA. By algorithmically scanning for transitions from `FAILURE`/`ERROR` to `SUCCESS` within the PR's commit array, we accurately mathematically derived the `independently_fixed_ci` metric.


### 4. DeepSeek Validation Pipeline

Heuristics alone are susceptible to false positives (e.g., `test_utils.py` being flagged as a unit test instead of a test helper). To have a more accurate count of the testing metrics, we executed a secondary validation phase using an LLM.

- We extracted all **76,733 unique test file paths** originally caught by the regex heuristic and batched them asynchronously through the **DeepSeek-V3.2 Chat API** (`deepseek-chat`).

- DeepSeek-V3.2 was prompted to strictly re-classify each path as exactly one of: `unit`, `integration`, `e2e`, or `not_a_test`.

- **Validation Drop-off**: DeepSeek evaluated the 76,733 paths and strictly rejected 54,005 paths (70.4%) as `not_a_test`, eliminating massive heuristic false positives. For the remaining valid tests, DeepSeek's intelligence radically shifted the distribution: Unit tests decreased from 73,766 to 19,850 (-73.1%), Integration decreased mildly from 2,091 to 1,999 (-4.4%), and E2E slightly increased from 876 to 879 (+0.3%). This mathematical purging proved the absolute necessity of LLM validation.

- **Why DeepSeek-V3.2?** We explicitly chose DeepSeek-V3.2 as the validation judge because none of the evaluated agents (Devin, Cursor, Copilot, Claude Code, OpenAI Codex) are powered by or inherently biased toward DeepSeek's specific base foundation models, ensuring a neutral, zero-contamination evaluation.

- Any PR where all test paths were downgraded to `not_a_test` by DeepSeek-V3.2 was purged from the dataset. This distilled our pool to a high-fidelity cohort of **8,807 Verified Test PRs** upon which all following math is based.

---

## 1. Type of Tests Distribution

### Overall
- **UNIT**: 8136 (92.4%)
- **INTEGRATION**: 432 (4.9%)
- **E2E**: 239 (2.7%)

![Overall Test Types](figures/1_test_type_overall.png)

### Grouped by Agent

![Test Types by Agent](figures/1_test_type_agent.png)

## 2. Test-to-Code Ratio

Ratio is calculated as `Test LOC / Prod LOC`.


> **Why is the median often > 1?** Test code typically requires extensive setup, teardown logic, mock object scaffolding, and multiple assertions per logical branch. It is historically expected and standard engineering practice for a comprehensive test suite to contain more Lines of Code than the actual production logic it is verifying.


> **Why cap at 10?** This ratio is visually capped at 10.0 to prevent extreme mathematical anomalies (e.g., 1000 lines of test for 1 line of prod code) from squashing the entire violin plot's scale, allowing the true distribution of the masses to remain visible. In this dataset, **2196 out of 8807 PRs** (24.9%) had an uncapped test-to-code ratio strictly greater than 10.0.

### Overall
- **Median Ratio**: 1.36

![Ratio Overall](figures/2_ratio_overall.png)

### Grouped by Agent

![Ratio by Agent](figures/2_ratio_agent.png)

## 3. Zero-Shot PRs (Exactly 1 Commit)

> **Note on Unmerged PRs:** For all success/failure metrics, PRs that have not been merged (whether explicitly Closed, Abandoned, or still Open/Pending) are clustered into the 'Failed' category, as they ultimately did not reach the threshold of human acceptance into the main branch.

### Overall Zero-Shot Success
- **Total 1-Commit PRs**: 5400
- **Succeeded**: 4479 (82.9%)
- **Failed**: 921 (17.1%)

![1 Commit Overall](figures/3_1c_overall.png)

### Grouped by Agent

![1 Commit by Agent](figures/3_1c_agent.png)

## 4. Trial and Error Commits (>1 Commit PRs)

### Overall Commits Statistics
| Metric | Value |
|---|---|
| Count | 3268 |
| Min | 2 |
| Max | 100 |
| Median | 4.00 |
| 95_CI_Lower | 4.00 |
| 95_CI_Upper | 5.00 |

### Grouped by Agent Statistics
| Agent | Count | Min | Max | Median | 95% CI Lower | 95% CI Upper |
|---|---|---|---|---|---|---|
| OpenAI_Codex | 806 | 2 | 100 | 3.00 | 3.00 | 3.00 |
| Devin | 692 | 2 | 100 | 5.00 | 4.00 | 5.00 |
| Claude_Code | 129 | 2 | 100 | 8.00 | 7.00 | 9.00 |
| Cursor | 183 | 2 | 50 | 5.00 | 4.00 | 6.00 |
| Copilot | 1458 | 2 | 100 | 5.00 | 5.00 | 5.00 |

![Multi Commits Graph](figures/4_multi_commits.png)

## 5. Iterative Success & Independent CI Fixes

> **Note on CI Failures**: By mathematical definition, an autonomous agent can only 'independently resolve' a Continuous Integration (CI) failure if it first submits a commit that triggers a CI `FAILURE` state, realizes its mistake, and iteratively submits a subsequent commit driving the CI state to `SUCCESS`. Therefore, exactly 1-Commit PRs are mathematically incapable of executing this behavior.

### Overall Iterative Success
- **Total Multi-Commit PRs**: 3268
- **Succeeded**: 1579 (48.3%)
- **Failed**: 1689 (51.7%)
- **Independently Resolved CI Failures**: 1312 (40.1% of all multi-commit PRs)

![Multi Overall](figures/5_multi_overall.png)

### Grouped by Agent

![Multi by Agent](figures/5_multi_agent.png)


![CI Fixed by Agent](figures/5_ci_fixed_agent.png)

## 6. Resolution Time (Succeeded PRs Only)

### Overall Resolution Time
- **Median Resolution**: 00:01:13
- **95% CI**: [00:01:05, 00:01:24]

![Res Overall](figures/6_res_overall.png)

### Grouped by Agent Resolution Time
| Agent | Median | 95% CI Low | 95% CI High |
|---|---|---|---|
| OpenAI_Codex | 00:00:31 | 00:00:30 | 00:00:34 |
| Claude_Code | 02:18:53 | 00:58:41 | 05:39:43 |
| Devin | 19:06:42 | 12:22:55 | 22:07:36 |
| Copilot | 25:38:06 | 22:26:06 | 30:41:18 |
| Cursor | 14:09:36 | 04:12:09 | 18:07:19 |

![Res Agent](figures/6_res_agent.png)

## 7. Influence of Repository Variables

### A. Spearman's Rank-Order Correlation ($\rho$)

Unlike Pearson’s correlation, Spearman evaluates the monotonic relationship between two variables using their ranks rather than raw values, making it highly resistant to massive outlier repositories like `linux` or `kubernetes`.


**Repo Stars vs. Test-to-Code Ratio**
- **$\rho$**: -0.1028
- **p-value**: 4.071e-22

**Repo Stars vs. Commit Count (Trial-and-Error)**
- **$\rho$**: 0.4760
- **p-value**: 0

**Repo Stars vs. Resolution Time (Successful Only)**
- **$\rho$**: 0.4505
- **p-value**: 1.842e-305


#### Visualization: Log-Log Scatters

![Spearman Scatters](figures/7_spearman_scatters.png)

### B. Kruskal-Wallis H Test: Test Type vs. Repo Size

The Kruskal-Wallis non-parametric test determines if the median size of repositories differs significantly across Unit, Integration, and E2E classes.

- **H-Statistic**: 59.8184
- **p-value**: 1.025e-13

Since $p < 0.05$, the distributions significantly differ. Running Dunn's post-hoc test:

#### Dunn's Test (p-values, Bonferroni adjusted)
| | Unit | Integration | E2E |
|---|---|---|---|
| **Unit** | - | 0.007121 | 1.533e-12 |
| **Integration** | 0.007121 | - | 0.0001759 |
| **E2E** | 1.533e-12 | 0.0001759 | - |

![Kruskal Boxplot](figures/7_kruskal_boxplot.png)
