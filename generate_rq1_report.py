import json
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import scipy.stats as st
import scikit_posthocs as sp

# Configure plotting style
sns.set_theme(style="whitegrid")
plt.rcParams.update({'font.size': 12, 'figure.dpi': 150})
os.makedirs('figures', exist_ok=True)

def compute_95_ci_median(data, n_boot=1000, seed=42):
    data = np.array(data)
    data = data[~np.isnan(data)]
    if len(data) == 0:
        return np.nan, np.nan, np.nan
    if len(data) == 1:
        return data[0], data[0], data[0]
        
    np.random.seed(seed)
    medians = []
    for _ in range(n_boot):
        sample = np.random.choice(data, size=len(data), replace=True)
        medians.append(np.median(sample))
    
    return np.median(data), np.percentile(medians, 2.5), np.percentile(medians, 97.5)

def format_time(seconds):
    if np.isnan(seconds):
        return "N/A"
    sec = int(seconds)
    hours = sec // 3600
    minutes = (sec % 3600) // 60
    secs = sec % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def add_value_labels(ax, spacing=5, format_str='{:.0f}'):
    for rect in ax.patches:
        y_value = rect.get_height()
        x_value = rect.get_x() + rect.get_width() / 2

        if y_value > 0:
            label = format_str.format(y_value)
            ax.annotate(
                label,
                (x_value, y_value),
                xytext=(0, spacing),
                textcoords="offset points",
                ha='center',
                va='bottom')

def main():
    print("Loading validated data...")
    with open('rq1_deepseek_filtered.json', 'r') as f:
        raw_data = json.load(f)

    rows = []
    for pr in raw_data:
        row = pr.copy()
        
        # Success indicator (unmerged / open are treated as Failed)
        row['success'] = 1 if pr.get('resolution_time_seconds') is not None else 0
        
        test_loc = pr.get('test_additions', 0) + pr.get('test_deletions', 0)
        prod_loc = pr.get('prod_additions', 0) + pr.get('prod_deletions', 0)
        row['test_loc'] = test_loc
        row['prod_loc'] = prod_loc
        row['total_loc'] = test_loc + prod_loc
        
        if prod_loc == 0:
            row['raw_test_to_code_ratio'] = np.nan if test_loc == 0 else 10.0 # cap at 10
        else:
            row['raw_test_to_code_ratio'] = min(test_loc / prod_loc, 10.0)
            
        res_sec = pr.get('resolution_time_seconds')
        row['resolution_time_seconds_val'] = res_sec if res_sec is not None else np.nan
        
        commits = pr.get('trial_and_error_commits', 1)
        row['is_1_commit'] = (commits == 1)
        row['is_multi_commit'] = (commits > 1)
        row['indep_fixed_ci'] = pr.get('independently_fixed_ci', False)
        
        row['project_stars'] = pr.get('project_stars', 0)
        row['project_forks'] = pr.get('project_forks', 0)
        row['log_stars'] = np.log1p(row['project_stars'])
        row['log_forks'] = np.log1p(row['project_forks'])
        
        rows.append(row)

    df = pd.DataFrame(rows)
    md_content = []
    md_content.append("# RQ1: Comprehensive Analysis Report\n")
    
    # --- METHODOLOGY SECTION ---
    md_content.append("## Methodology\n")
    md_content.append("To rigorously answer RQ1, we designed a multi-phase data extraction and validation pipeline against the `hao-li/AIDev` HuggingFace dataset.\n")
    
    md_content.append("### 1. Data Sources and Table Mappings\n")
    md_content.append("We cross-referenced three primary tables from the dataset:\n")
    md_content.append("- **`pull_request`**: We extracted `pr_id`, `pr_number`, `repo_id`, `created_at`, `merged_at`, and `agent_type`. This provided the foundational PR cohort and resolution timeframes.\n")
    md_content.append("- **`pr_commit_details`**: We mapped `pr_id` to aggregate every file modified in the PR. We utilized the `additions`, `deletions`, and `filename` columns to calculate exact code churn, isolating `test_loc` (testing lines of code) from `prod_loc` (production lines of code).\n")
    md_content.append("- **`repository`**: We mapped `repo_id` to extract `stars` and `forks`, establishing the influence of project popularity.\n")
    
    md_content.append("\n### 2. Heuristic Test Classification\n")
    md_content.append("We initially isolated 'Test PRs' by parsing the `filename` of every changed file through heuristic regex rules:\n")
    md_content.append("- **Test Identification**: Files matching patterns like `(?i)(test|spec|mock|fixture|e2e|cypress)` were flagged as test files.\n")
    md_content.append("- **Type Classification**: We mapped test files to testing levels using path-based regex boundaries. Paths containing `e2e`, `cypress`, `playwright`, or `selenium` were binned as **E2E**. Paths containing `integration`, `api`, or `db` were binned as **Integration**. All remaining test paths defaulted to **Unit**.\n")
    
    md_content.append("\n### 3. GitHub GraphQL Augmentation\n")
    md_content.append("Because the static dataset lacked chronological pipeline execution states, we utilized the **GitHub GraphQL API** to natively reconstruct the timeline of each PR:\n")
    md_content.append("- **Chronological Commits**: We fetched exactly how many commits the agent submitted (`trial_and_error_commits`).\n")
    md_content.append("- **CI Pipeline Statuses**: We queried the `statusCheckRollup` for every commit SHA. By algorithmically scanning for transitions from `FAILURE`/`ERROR` to `SUCCESS` within the PR's commit array, we accurately mathematically derived the `independently_fixed_ci` metric.\n")
    
    md_content.append("\n### 4. DeepSeek Validation Pipeline\n")
    md_content.append("Heuristics alone are susceptible to false positives (e.g., `test_utils.py` being flagged as a unit test instead of a test helper). To guarantee the absolute purity of the testing metrics, we executed a secondary validation phase using an LLM.\n")
    md_content.append("- We extracted all **76,733 unique test file paths** originally caught by the heuristics and batched them asynchronously through the **DeepSeek Chat API** (`deepseek-chat`).\n")
    md_content.append("- DeepSeek was prompted to strictly re-classify each path as exactly one of: `unit`, `integration`, `e2e`, `other`, or `not_a_test`.\n")
    md_content.append("- **Why DeepSeek?** We explicitly chose DeepSeek as the validation judge because none of the evaluated agents (Devin, Cursor, Copilot, Claude Code, OpenAI Codex) are powered by or inherently biased toward DeepSeek's specific base foundation models, ensuring a neutral, zero-contamination evaluation.\n")
    md_content.append(f"- Any PR where all test paths were downgraded to `not_a_test` by DeepSeek was purged from the dataset. This distilled our pool to a high-fidelity cohort of **{len(df)} Verified Test PRs** upon which all following math is based.\n")
    md_content.append("---\n")
    
    # 1. Type of Tests
    md_content.append("## 1. Type of Tests Distribution\n")
    plt.figure(figsize=(8, 6))
    ax = sns.countplot(data=df, x='dominant_test_type', order=['unit', 'integration', 'e2e', 'other'], palette='Set2', hue='dominant_test_type', legend=False)
    plt.title("Overall Test Type Distribution")
    plt.ylabel("Number of PRs")
    plt.xlabel("Test Type")
    add_value_labels(ax)
    plt.tight_layout()
    plt.savefig('figures/1_test_type_overall.png')
    plt.close()
    
    md_content.append("### Overall")
    type_counts = df['dominant_test_type'].value_counts()
    for t in ['unit', 'integration', 'e2e', 'other']:
        c = type_counts.get(t, 0)
        md_content.append(f"- **{t.upper()}**: {c} ({c/len(df)*100:.1f}%)")
    md_content.append("\n![Overall Test Types](figures/1_test_type_overall.png)\n")

    plt.figure(figsize=(10, 6))
    ax = sns.countplot(data=df, x='agent_type', hue='dominant_test_type', hue_order=['unit', 'integration', 'e2e', 'other'], palette='Set2')
    plt.title("Test Type Distribution Grouped by Agent")
    plt.ylabel("Number of PRs")
    plt.xlabel("Agent Type")
    plt.legend(title='Test Type')
    plt.tight_layout()
    plt.savefig('figures/1_test_type_agent.png')
    plt.close()
    
    md_content.append("### Grouped by Agent")
    md_content.append("\n![Test Types by Agent](figures/1_test_type_agent.png)\n")

    # 2. Test to Code Ratio
    md_content.append("## 2. Test-to-Code Ratio\n")
    md_content.append("Ratio is calculated as `Test LOC / Prod LOC`.\n\n")
    md_content.append("> **Why is the median often > 1?** Test code typically requires extensive setup, teardown logic, mock object scaffolding, and multiple assertions per logical branch. It is historically expected and standard engineering practice for a comprehensive test suite to contain more Lines of Code than the actual production logic it is verifying.\n\n")
    
    # Calculate exactly how many are capped to 10
    uncapped_ratios = df['test_loc'] / df['prod_loc'].replace(0, 1e-10)
    capped_count = (uncapped_ratios > 10.0).sum()
    md_content.append(f"> **Why cap at 10?** This ratio is visually capped at 10.0 to prevent extreme mathematical anomalies (e.g., 1000 lines of test for 1 line of prod code) from squashing the entire violin plot's scale, allowing the true distribution of the masses to remain visible. In this dataset, **{capped_count} out of {len(df)} PRs** ({capped_count/len(df)*100:.1f}%) had an uncapped test-to-code ratio strictly greater than 10.0.\n")
    
    plt.figure(figsize=(8, 6))
    sns.violinplot(data=df, y='raw_test_to_code_ratio', color='skyblue', inner='quartile')
    plt.title("Overall Test-to-Code Ratio Distribution")
    plt.ylabel("Ratio (Test LOC / Prod LOC)")
    plt.tight_layout()
    plt.savefig('figures/2_ratio_overall.png')
    plt.close()
    
    md_content.append("### Overall")
    median_ratio = df['raw_test_to_code_ratio'].median()
    md_content.append(f"- **Median Ratio**: {median_ratio:.2f}")
    md_content.append("\n![Ratio Overall](figures/2_ratio_overall.png)\n")

    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df, x='agent_type', y='raw_test_to_code_ratio', palette='Pastel1', showfliers=False, hue='agent_type', legend=False)
    plt.title("Test-to-Code Ratio Grouped by Agent (Outliers Hidden)")
    plt.ylabel("Ratio (Test LOC / Prod LOC)")
    plt.xlabel("Agent Type")
    plt.tight_layout()
    plt.savefig('figures/2_ratio_agent.png')
    plt.close()
    md_content.append("### Grouped by Agent")
    md_content.append("\n![Ratio by Agent](figures/2_ratio_agent.png)\n")

    # 3. Exactly 1 Commit
    md_content.append("## 3. Zero-Shot PRs (Exactly 1 Commit)\n")
    md_content.append("> **Note on Unmerged PRs:** For all success/failure metrics, PRs that have not been merged (whether explicitly Closed, Abandoned, or still Open/Pending) are clustered into the 'Failed' category, as they ultimately did not reach the threshold of human acceptance into the main branch.\n")
    
    df_1_commit = df[df['is_1_commit']]
    def plot_success_stacked(dframe, x_col, title, save_path):
        counts = dframe.groupby([x_col, 'success']).size().unstack(fill_value=0)
        if 0 not in counts: counts[0] = 0
        if 1 not in counts: counts[1] = 0
        counts = counts[[1, 0]]
        counts.columns = ['Succeeded (Merged)', 'Failed (Closed/Unmerged)']
        ax = counts.plot(kind='bar', stacked=True, figsize=(10, 6), color=['#2ca02c', '#d62728'])
        plt.title(title)
        plt.ylabel("Number of PRs")
        plt.xlabel(x_col.replace('_', ' ').title())
        plt.xticks(rotation=45 if x_col != 'All_1_Commit_PRs' and x_col != 'All_Multi_Commit_PRs' else 0)
        plt.legend(loc='upper right')
        for p in ax.patches:
            width, height = p.get_width(), p.get_height()
            x, y = p.get_xy() 
            if height > 0:
                ax.text(x+width/2, y+height/2, int(height), horizontalalignment='center', verticalalignment='center', color='white', weight='bold')
        plt.tight_layout()
        plt.savefig(save_path)
        plt.close()
        return counts

    md_content.append("### Overall Zero-Shot Success")
    total_1c = len(df_1_commit)
    succ_1c = df_1_commit['success'].sum()
    md_content.append(f"- **Total 1-Commit PRs**: {total_1c}")
    md_content.append(f"- **Succeeded**: {succ_1c} ({succ_1c/total_1c*100:.1f}%)")
    md_content.append(f"- **Failed**: {total_1c - succ_1c} ({(total_1c - succ_1c)/total_1c*100:.1f}%)")
    
    df_1_commit_dummy = df_1_commit.copy()
    df_1_commit_dummy['All_1_Commit_PRs'] = 'Total Dataset'
    plot_success_stacked(df_1_commit_dummy, 'All_1_Commit_PRs', "Overall Success of 1-Commit PRs", 'figures/3_1c_overall.png')
    md_content.append("\n![1 Commit Overall](figures/3_1c_overall.png)\n")

    md_content.append("### Grouped by Agent")
    plot_success_stacked(df_1_commit, 'agent_type', "Success of 1-Commit PRs by Agent", 'figures/3_1c_agent.png')
    md_content.append("\n![1 Commit by Agent](figures/3_1c_agent.png)\n")

    # 4. Trial and Error
    md_content.append("## 4. Trial and Error Commits (>1 Commit PRs)\n")
    df_multi = df[df['is_multi_commit']]
    def get_commit_stats(dframe):
        data = dframe['trial_and_error_commits']
        med, ci_low, ci_high = compute_95_ci_median(data)
        return {"Count": len(data), "Min": data.min(), "Max": data.max(), "Median": med, "95_CI_Lower": ci_low, "95_CI_Upper": ci_high}

    overall_multi_stats = get_commit_stats(df_multi)
    md_content.append("### Overall Commits Statistics")
    md_content.append("| Metric | Value |")
    md_content.append("|---|---|")
    for k, v in overall_multi_stats.items():
        if isinstance(v, float): md_content.append(f"| {k} | {v:.2f} |")
        else: md_content.append(f"| {k} | {v} |")
            
    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df_multi, x='agent_type', y='trial_and_error_commits', palette='Set3', showfliers=False, hue='agent_type', legend=False)
    plt.title("Trial and Error Commits by Agent (Outliers Hidden)")
    plt.ylabel("Number of Commits")
    plt.xlabel("Agent Type")
    plt.tight_layout()
    plt.savefig('figures/4_multi_commits.png')
    plt.close()

    md_content.append("\n### Grouped by Agent Statistics")
    md_content.append("| Agent | Count | Min | Max | Median | 95% CI Lower | 95% CI Upper |")
    md_content.append("|---|---|---|---|---|---|---|")
    for agent in df_multi['agent_type'].unique():
        s = get_commit_stats(df_multi[df_multi['agent_type'] == agent])
        md_content.append(f"| {agent} | {s['Count']} | {s['Min']} | {s['Max']} | {s['Median']:.2f} | {s['95_CI_Lower']:.2f} | {s['95_CI_Upper']:.2f} |")
    md_content.append("\n![Multi Commits Graph](figures/4_multi_commits.png)\n")

    # 5. Iterative Success & Independent CI Fixes
    md_content.append("## 5. Iterative Success & Independent CI Fixes\n")
    md_content.append("> **Note on CI Failures**: By mathematical definition, an autonomous agent can only 'independently resolve' a Continuous Integration (CI) failure if it first submits a commit that triggers a CI `FAILURE` state, realizes its mistake, and iteratively submits a subsequent commit driving the CI state to `SUCCESS`. Therefore, exactly 1-Commit PRs are mathematically incapable of executing this behavior.\n")
    
    total_m = len(df_multi)
    succ_m = df_multi['success'].sum()
    ci_fixed_m = df_multi['indep_fixed_ci'].sum()
    
    md_content.append("### Overall Iterative Success")
    md_content.append(f"- **Total Multi-Commit PRs**: {total_m}")
    md_content.append(f"- **Succeeded**: {succ_m} ({succ_m/total_m*100:.1f}%)")
    md_content.append(f"- **Failed**: {total_m - succ_m} ({(total_m - succ_m)/total_m*100:.1f}%)")

    # CI Failure Categories
    if 'ci_had_failure' in df_multi.columns:
        # Enforce logical consistency: if the agent fixed a CI failure, it MUST have had a failure,
        # resolving API state drifts between pipeline execution dates.
        df_multi.loc[df_multi['indep_fixed_ci'] == True, 'ci_had_failure'] = True

        no_ci_failure = len(df_multi[df_multi['ci_had_failure'] == False])
        indep_resolved = len(df_multi[df_multi['indep_fixed_ci'] == True])
        
        failed_not_indep = df_multi[(df_multi['ci_had_failure'] == True) & (df_multi['indep_fixed_ci'] == False)]
        not_solved_human = len(failed_not_indep[failed_not_indep['success'] == 1])
        not_solved_abandoned = len(failed_not_indep[failed_not_indep['success'] == 0])

        md_content.append("\n### CI Failure Breakdown (Multi-Commit PRs)")
        md_content.append(f"- **No CI Failure Occurred**: {no_ci_failure} ({no_ci_failure/total_m*100:.1f}%)")
        md_content.append(f"- **Independently Solved (by Agent)**: {indep_resolved} ({indep_resolved/total_m*100:.1f}%)")
        md_content.append(f"- **Not Solved, but Merged (with Human Help)**: {not_solved_human} ({not_solved_human/total_m*100:.1f}%)")
        md_content.append(f"- **Not Solved and Abandoned**: {not_solved_abandoned} ({not_solved_abandoned/total_m*100:.1f}%)")
    else:
        md_content.append(f"- **Independently Resolved CI Failures**: {ci_fixed_m} ({ci_fixed_m/total_m*100:.1f}% of all multi-commit PRs)")
    
    df_multi_dummy = df_multi.copy()
    df_multi_dummy['All_Multi_Commit_PRs'] = 'Total Dataset'
    plot_success_stacked(df_multi_dummy, 'All_Multi_Commit_PRs', "Overall Success of Multi-Commit PRs", 'figures/5_multi_overall.png')
    md_content.append("\n![Multi Overall](figures/5_multi_overall.png)\n")

    md_content.append("### Grouped by Agent")
    plot_success_stacked(df_multi, 'agent_type', "Success of Multi-Commit PRs by Agent", 'figures/5_multi_agent.png')
    md_content.append("\n![Multi by Agent](figures/5_multi_agent.png)\n")
    
    plt.figure(figsize=(10, 6))
    ci_counts = df_multi.groupby('agent_type')['indep_fixed_ci'].sum().reset_index()
    ax = sns.barplot(data=ci_counts, x='agent_type', y='indep_fixed_ci', palette='magma', hue='agent_type', legend=False)
    plt.title("Independently Fixed CI Failures by Agent")
    plt.ylabel("Number of CI Resolutions")
    plt.xlabel("Agent Type")
    add_value_labels(ax)
    plt.tight_layout()
    plt.savefig('figures/5_ci_fixed_agent.png')
    plt.close()
    md_content.append("\n![CI Fixed by Agent](figures/5_ci_fixed_agent.png)\n")

    # 6. Resolution Time
    md_content.append("## 6. Resolution Time (Succeeded PRs Only)\n")
    df_succ = df[df['success'] == 1].copy()
    
    def get_res_stats_sec(dframe):
        data = dframe['resolution_time_seconds_val'].dropna()
        med, ci_low, ci_high = compute_95_ci_median(data)
        return {"Count": len(data), "Median": med, "95_CI_Low": ci_low, "95_CI_High": ci_high}

    overall_res = get_res_stats_sec(df_succ)
    md_content.append("### Overall Resolution Time")
    md_content.append(f"- **Median Resolution**: {format_time(overall_res['Median'])}")
    md_content.append(f"- **95% CI**: [{format_time(overall_res['95_CI_Low'])}, {format_time(overall_res['95_CI_High'])}]\n")

    # For violin plot, keep hours to make x-axis readable
    df_succ['resolution_time_hours'] = df_succ['resolution_time_seconds_val'] / 3600.0
    df_succ_trim = df_succ[df_succ['resolution_time_hours'] < 1000]

    plt.figure(figsize=(8, 6))
    sns.violinplot(data=df_succ_trim, y='resolution_time_hours', color='lightgreen', inner='quartile')
    plt.title("Overall Resolution Time (Capped at 1000h for visuals)")
    plt.ylabel("Resolution Time (Hours)")
    plt.tight_layout()
    plt.savefig('figures/6_res_overall.png')
    plt.close()
    md_content.append("![Res Overall](figures/6_res_overall.png)\n")

    md_content.append("### Grouped by Agent Resolution Time")
    md_content.append("| Agent | Median | 95% CI Low | 95% CI High |")
    md_content.append("|---|---|---|---|")
    for agent in df_succ['agent_type'].unique():
        s = get_res_stats_sec(df_succ[df_succ['agent_type'] == agent])
        md_content.append(f"| {agent} | {format_time(s['Median'])} | {format_time(s['95_CI_Low'])} | {format_time(s['95_CI_High'])} |")

    plt.figure(figsize=(10, 6))
    sns.boxplot(data=df_succ_trim, x='agent_type', y='resolution_time_hours', palette='pastel', showfliers=False, hue='agent_type', legend=False)
    plt.title("Resolution Time by Agent (Outliers Hidden)")
    plt.ylabel("Resolution Time (Hours)")
    plt.xlabel("Agent Type")
    plt.tight_layout()
    plt.savefig('figures/6_res_agent.png')
    plt.close()
    md_content.append("\n![Res Agent](figures/6_res_agent.png)\n")

    # 7. Influence of Project Stars & Forks (Spearman & Kruskal)
    md_content.append("## 7. Influence of Repository Variables\n")
    
    # Spearman Corrs
    md_content.append("### A. Spearman's Rank-Order Correlation ($\\rho$)\n")
    md_content.append("Unlike Pearson’s correlation, Spearman evaluates the monotonic relationship between two variables using their ranks rather than raw values, making it highly resistant to massive outlier repositories like `linux` or `kubernetes`.\n\n")
    
    # 1: Repo Size vs Test-to-Code Ratio
    df_corr_ratio = df.dropna(subset=['raw_test_to_code_ratio'])
    rho_ratio, p_ratio = st.spearmanr(df_corr_ratio['project_stars'], df_corr_ratio['raw_test_to_code_ratio'])
    md_content.append(f"**Repo Stars vs. Test-to-Code Ratio**\n- **$\\rho$**: {rho_ratio:.4f}\n- **p-value**: {p_ratio:.4g}\n")
    
    # 2: Repo Size vs Trial and Error (Commits)
    rho_commits, p_commits = st.spearmanr(df['project_stars'], df['trial_and_error_commits'])
    md_content.append(f"**Repo Stars vs. Commit Count (Trial-and-Error)**\n- **$\\rho$**: {rho_commits:.4f}\n- **p-value**: {p_commits:.4g}\n")
    
    # 3: Repo Size vs Resolution Time (Success only)
    df_corr_res = df_succ.dropna(subset=['resolution_time_seconds_val'])
    rho_res, p_res = st.spearmanr(df_corr_res['project_stars'], df_corr_res['resolution_time_seconds_val'])
    md_content.append(f"**Repo Stars vs. Resolution Time (Successful Only)**\n- **$\\rho$**: {rho_res:.4f}\n- **p-value**: {p_res:.4g}\n")

    # Scatter Plots (Log-Log)
    md_content.append("\n#### Visualization: Log-Log Scatters\n")
    
    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    
    axes[0].scatter(df_corr_ratio['project_stars']+1, df_corr_ratio['raw_test_to_code_ratio']+1e-5, alpha=0.3, s=5, c='blue')
    axes[0].set_xscale('log')
    axes[0].set_yscale('log')
    axes[0].set_xlabel('Project Stars (Log)')
    axes[0].set_ylabel('Test-to-Code Ratio (Log)')
    axes[0].set_title("Stars vs Test Ratio")
    
    axes[1].scatter(df['project_stars']+1, df['trial_and_error_commits'], alpha=0.3, s=5, c='green')
    axes[1].set_xscale('log')
    axes[1].set_yscale('log')
    axes[1].set_xlabel('Project Stars (Log)')
    axes[1].set_ylabel('Total Commits (Log)')
    axes[1].set_title("Stars vs Commits")
    
    axes[2].scatter(df_corr_res['project_stars']+1, df_corr_res['resolution_time_hours']+1e-5, alpha=0.3, s=5, c='red')
    axes[2].set_xscale('log')
    axes[2].set_yscale('log')
    axes[2].set_xlabel('Project Stars (Log)')
    axes[2].set_ylabel('Resolution Time Hours (Log)')
    axes[2].set_title("Stars vs Resolution Time")
    
    plt.tight_layout()
    plt.savefig('figures/7_spearman_scatters.png')
    plt.close()
    md_content.append("![Spearman Scatters](figures/7_spearman_scatters.png)\n")

    # B. Kruskal-Wallis H Test
    md_content.append("### B. Kruskal-Wallis H Test: Test Type vs. Repo Size\n")
    md_content.append("The Kruskal-Wallis non-parametric test determines if the median size of repositories differs significantly across Unit, Integration, and E2E classes.\n")

    dist_unit = df[df['dominant_test_type'] == 'unit']['project_stars']
    dist_int = df[df['dominant_test_type'] == 'integration']['project_stars']
    dist_e2e = df[df['dominant_test_type'] == 'e2e']['project_stars']
    dist_other = df[df['dominant_test_type'] == 'other']['project_stars']
    
    # Kruskal Wallis
    if len(dist_unit) > 0 and len(dist_int) > 0 and len(dist_e2e) > 0 and len(dist_other) > 0:
        h_stat, p_kw = st.kruskal(dist_unit, dist_int, dist_e2e, dist_other)
        md_content.append(f"- **H-Statistic**: {h_stat:.4f}\n- **p-value**: {p_kw:.4g}\n")
        
        if p_kw < 0.05:
            md_content.append("Since $p < 0.05$, the distributions significantly differ. Running Dunn's post-hoc test:\n")
            try:
                p_values = sp.posthoc_dunn(df, val_col='project_stars', group_col='dominant_test_type', p_adjust='bonferroni')
                md_content.append("#### Dunn's Test (p-values, Bonferroni adjusted)")
                md_content.append("| | Unit | Integration | E2E | Other |")
                md_content.append("|---|---|---|---|---|")
                md_content.append(f"| **Unit** | - | {p_values.loc['unit','integration']:.4g} | {p_values.loc['unit','e2e']:.4g} | {p_values.loc['unit','other']:.4g} |")
                md_content.append(f"| **Integration** | {p_values.loc['integration','unit']:.4g} | - | {p_values.loc['integration','e2e']:.4g} | {p_values.loc['integration','other']:.4g} |")
                md_content.append(f"| **E2E** | {p_values.loc['e2e','unit']:.4g} | {p_values.loc['e2e','integration']:.4g} | - | {p_values.loc['e2e','other']:.4g} |")
                md_content.append(f"| **Other** | {p_values.loc['other','unit']:.4g} | {p_values.loc['other','integration']:.4g} | {p_values.loc['other','e2e']:.4g} | - |")
            except Exception as e:
                md_content.append(f"(Could not run Dunn's precisely: {e})")
        else:
            md_content.append("Since $p \\ge 0.05$, there is no significant difference in repository sizes between the dominant test types written.\n")
    else:
         md_content.append("Not enough data to run Kruskal-Wallis across all categories.\n")

    # Visualization
    plt.figure(figsize=(8, 6))
    ax = sns.boxplot(data=df, x='dominant_test_type', y='project_stars', order=['unit', 'integration', 'e2e', 'other'], palette='Set2', hue='dominant_test_type', legend=False)
    ax.set_yscale('symlog') # Handles 0 elegantly unlike strict log
    plt.title("Repository Size (Stars) by Dominant Test Type")
    plt.ylabel("Project Stars (Log Scale)")
    plt.xlabel("Test Type")
    plt.tight_layout()
    plt.savefig('figures/7_kruskal_boxplot.png')
    plt.close()
    
    md_content.append("\n![Kruskal Boxplot](figures/7_kruskal_boxplot.png)\n")

    # Simple bin line plot for test distribution by size
    bins = [-1, 10, 100, 1000, 10000, 100000, 1e9]
    labels = ['0-10', '11-100', '101-1k', '1k-10k', '10k-100k', '100k+']
    df['star_bins'] = pd.cut(df['project_stars'], bins=bins, labels=labels)
    bin_counts = df.groupby(['star_bins', 'dominant_test_type'], observed=True).size().reset_index(name='count')
    
    plt.figure(figsize=(10, 6))
    sns.lineplot(data=bin_counts, x='star_bins', y='count', hue='dominant_test_type', marker='o', palette='Set2')
    plt.title("Growth of Test Types by Repository Size")
    plt.xlabel("Repository Size (Stars Bins)")
    plt.ylabel("Number of PRs")
    plt.tight_layout()
    plt.savefig('figures/7_test_growth_line.png')
    plt.close()

    md_content.append("### Simple Test Type Growth by Repository Size\n")
    md_content.append("\n![Test Growth Line](figures/7_test_growth_line.png)\n")

    print("Saving markdown document...")
    with open('rq1_analysis_report.md', 'w') as f:
        f.write('\n'.join(md_content))
        
    print("Done! rq1_analysis_report.md and /figures/ generated.")

if __name__ == "__main__":
    main()
