# RQ1: Comprehensive Analysis Report

## Methodology

To rigorously answer RQ1, we designed a multi-phase data extraction and validation pipeline against the `hao-li/AIDev` HuggingFace dataset.

### 1. Data Sources and Table Mappings

We cross-referenced three primary tables from the dataset:

- **`pull_request`**: We extracted `pr_id`, `pr_number`, `repo_id`, `created_at`, `merged_at`, and `agent_type`. This provided the foundational PR cohort and resolution timeframes.

- **`pr_commit_details`**: We mapped `pr_id` to aggregate every file modified in the PR. We utilized the `additions`, `deletions`, and `filename` columns to calculate exact code churn, isolating `test_loc` (testing lines of code) from `prod_loc` (production lines of code).

- **`repository`**: We mapped `repo_id` to extract `stars` and `forks`, establishing the influence of project popularity.


### 2. Heuristic Test Classification

We initially isolated 'Test PRs' by parsing the `filename` of every changed file through heuristic regex rules:

- **Test Identification**: Files matching patterns like `(?i)(test|spec|mock|fixture|e2e|cypress)` were flagged as test files.

- **Type Classification**: We mapped test files to testing levels using path-based regex boundaries. Paths containing `e2e`, `cypress`, `playwright`, or `selenium` were binned as **E2E**. Paths containing `integration`, `api`, or `db` were binned as **Integration**. All remaining test paths defaulted to **Unit**.


### 3. GitHub GraphQL Augmentation

Because the static dataset lacked chronological pipeline execution states, we utilized the **GitHub GraphQL API** to natively reconstruct the timeline of each PR:

- **Chronological Commits**: We fetched exactly how many commits the agent submitted (`trial_and_error_commits`).

- **CI Pipeline Statuses**: We queried the `statusCheckRollup` for every commit SHA. By algorithmically scanning for transitions from `FAILURE`/`ERROR` to `SUCCESS` within the PR's commit array, we accurately mathematically derived the `independently_fixed_ci` metric.


### 4. DeepSeek Validation Pipeline

Heuristics alone are susceptible to false positives (e.g., `test_utils.py` being flagged as a unit test instead of a test helper). To guarantee the absolute purity of the testing metrics, we executed a secondary validation phase using an LLM.

- We extracted all **76,733 unique test file paths** originally caught by the heuristics and batched them asynchronously through the **DeepSeek Chat API** (`deepseek-chat`).

- DeepSeek was prompted to strictly re-classify each path as exactly one of: `unit`, `integration`, `e2e`, `other`, or `not_a_test`.

- **Why DeepSeek?** We explicitly chose DeepSeek as the validation judge because none of the evaluated agents (Devin, Cursor, Copilot, Claude Code, OpenAI Codex) are powered by or inherently biased toward DeepSeek's specific base foundation models, ensuring a neutral, zero-contamination evaluation.

- Any PR where all test paths were downgraded to `not_a_test` by DeepSeek was purged from the dataset. This distilled our pool to a high-fidelity cohort of **6366 Verified Test PRs** upon which all following math is based.

---

## 1. Type of Tests Distribution

### Overall
- **UNIT**: 5024 (78.9%)
- **INTEGRATION**: 321 (5.0%)
- **E2E**: 244 (3.8%)
- **OTHER**: 777 (12.2%)

![Overall Test Types](figures/1_test_type_overall.png)

### Grouped by Agent

![Test Types by Agent](figures/1_test_type_agent.png)

## 2. Test-to-Code Ratio

Ratio is calculated as `Test LOC / Prod LOC`.


> **Why is the median often > 1?** Test code typically requires extensive setup, teardown logic, mock object scaffolding, and multiple assertions per logical branch. It is historically expected and standard engineering practice for a comprehensive test suite to contain more Lines of Code than the actual production logic it is verifying.


> **Why cap at 10?** This ratio is visually capped at 10.0 to prevent extreme mathematical anomalies (e.g., 1000 lines of test for 1 line of prod code) from squashing the entire violin plot's scale, allowing the true distribution of the masses to remain visible. In this dataset, **1484 out of 6366 PRs** (23.3%) had an uncapped test-to-code ratio strictly greater than 10.0.

### Overall
- **Median Ratio**: 1.15

![Ratio Overall](figures/2_ratio_overall.png)

### Grouped by Agent

![Ratio by Agent](figures/2_ratio_agent.png)

## 3. Zero-Shot PRs (Exactly 1 Commit)

> **Note on Unmerged PRs:** For all success/failure metrics, PRs that have not been merged (whether explicitly Closed, Abandoned, or still Open/Pending) are clustered into the 'Failed' category, as they ultimately did not reach the threshold of human acceptance into the main branch.

### Overall Zero-Shot Success
- **Total 1-Commit PRs**: 3032
- **Succeeded**: 2452 (80.9%)
- **Failed**: 580 (19.1%)

![1 Commit Overall](figures/3_1c_overall.png)

### Grouped by Agent

![1 Commit by Agent](figures/3_1c_agent.png)

## 4. Trial and Error Commits (>1 Commit PRs)

### Overall Commits Statistics
| Metric | Value |
|---|---|
| Count | 3197 |
| Min | 2 |
| Max | 100 |
| Median | 4.00 |
| 95_CI_Lower | 4.00 |
| 95_CI_Upper | 5.00 |

### Grouped by Agent Statistics
| Agent | Count | Min | Max | Median | 95% CI Lower | 95% CI Upper |
|---|---|---|---|---|---|---|
| OpenAI_Codex | 790 | 2 | 100 | 3.00 | 3.00 | 3.00 |
| Devin | 682 | 2 | 100 | 5.00 | 4.00 | 5.00 |
| Claude_Code | 127 | 2 | 100 | 8.00 | 7.00 | 9.00 |
| Cursor | 179 | 2 | 50 | 5.00 | 4.00 | 6.00 |
| Copilot | 1419 | 2 | 100 | 5.00 | 5.00 | 5.00 |

![Multi Commits Graph](figures/4_multi_commits.png)

## 5. Iterative Success & Independent CI Fixes

> **Note on CI Failures**: By mathematical definition, an autonomous agent can only 'independently resolve' a Continuous Integration (CI) failure if it first submits a commit that triggers a CI `FAILURE` state, realizes its mistake, and iteratively submits a subsequent commit driving the CI state to `SUCCESS`. Therefore, exactly 1-Commit PRs are mathematically incapable of executing this behavior.

### Overall Iterative Success
- **Total Multi-Commit PRs**: 3197
- **Succeeded**: 1547 (48.4%)
- **Failed**: 1650 (51.6%)

### CI Failure Breakdown (Multi-Commit PRs)
- **No CI Failure Occurred**: 875 (27.4%)
- **Independently Solved (by Agent)**: 1285 (40.2%)
- **Not Solved, but Merged (with Human Help)**: 299 (9.4%)
- **Not Solved and Abandoned**: 738 (23.1%)

![Multi Overall](figures/5_multi_overall.png)

### Grouped by Agent

![Multi by Agent](figures/5_multi_agent.png)


![CI Fixed by Agent](figures/5_ci_fixed_agent.png)

## 6. Resolution Time (Succeeded PRs Only)

### Overall Resolution Time
- **Median Resolution**: 00:03:08
- **95% CI**: [00:02:31, 00:03:49]

![Res Overall](figures/6_res_overall.png)

### Grouped by Agent Resolution Time
| Agent | Median | 95% CI Low | 95% CI High |
|---|---|---|---|
| OpenAI_Codex | 00:00:36 | 00:00:33 | 00:00:41 |
| Claude_Code | 01:45:08 | 00:58:41 | 04:48:20 |
| Devin | 19:06:42 | 12:46:17 | 22:07:36 |
| Copilot | 25:38:06 | 22:17:02 | 30:41:13 |
| Cursor | 14:03:38 | 04:31:52 | 17:53:04 |

![Res Agent](figures/6_res_agent.png)

## 7. Influence of Repository Variables

### A. Spearman's Rank-Order Correlation ($\rho$)

Unlike Pearson’s correlation, Spearman evaluates the monotonic relationship between two variables using their ranks rather than raw values, making it highly resistant to massive outlier repositories like `linux` or `kubernetes`.


**Repo Stars vs. Test-to-Code Ratio**
- **$\rho$**: -0.0911
- **p-value**: 3.224e-13

**Repo Stars vs. Commit Count (Trial-and-Error)**
- **$\rho$**: 0.4329
- **p-value**: 4.338e-289

**Repo Stars vs. Resolution Time (Successful Only)**
- **$\rho$**: 0.4955
- **p-value**: 8.142e-253


#### Visualization: Log-Log Scatters

![Spearman Scatters](figures/7_spearman_scatters.png)

### B. Kruskal-Wallis H Test: Test Type vs. Repo Size

The Kruskal-Wallis non-parametric test determines if the median size of repositories differs significantly across Unit, Integration, and E2E classes.

- **H-Statistic**: 173.3502
- **p-value**: 2.406e-37

Since $p < 0.05$, the distributions significantly differ. Running Dunn's post-hoc test:

#### Dunn's Test (p-values, Bonferroni adjusted)
| | Unit | Integration | E2E | Other |
|---|---|---|---|---|
| **Unit** | - | 1 | 0.04801 | 1.506e-35 |
| **Integration** | 1 | - | 0.3843 | 2.374e-13 |
| **E2E** | 0.04801 | 0.3843 | - | 1.615e-18 |
| **Other** | 1.506e-35 | 2.374e-13 | 1.615e-18 | - |

![Kruskal Boxplot](figures/7_kruskal_boxplot.png)

### Simple Test Type Growth by Repository Size


![Test Growth Line](figures/7_test_growth_line.png)
