import json
import pandas as pd
import numpy as np
import statsmodels.api as sm
import matplotlib.pyplot as plt
import seaborn as sns
import os

def run_logistic_regression(df):
    """Executes a multivariate logistic regression evaluating PR Success predictors."""
    
    # Dependent Variable
    y = df['success']
    
    # We will use raw_test_to_code_ratio, trial_and_error_commits, log_stars
    X = df[['raw_test_to_code_ratio', 'trial_and_error_commits', 'log_stars']].copy()
    
    # Categorical Variable: dominant_test_type
    # We need to one-hot encode it. Let's make "unit" the baseline, 
    # so we include 'integration' and 'e2e' as dummy variables.
    dummies = pd.get_dummies(df['dominant_test_type'], drop_first=False)
    
    # Assuming 'unit' is present, drop it to serve as the baseline
    if 'unit' in dummies.columns:
        dummies = dummies.drop(columns=['unit'])
        
    X = pd.concat([X, dummies], axis=1)
    
    # Add constant intercept
    X = sm.add_constant(X)
    
    # We must ensure there are no NaNs in X
    valid_idx = X.notna().all(axis=1) & y.notna()
    X_valid = X[valid_idx]
    y_valid = y[valid_idx]
    
    # Ensure boolean columns are numeric
    X_valid = X_valid.astype(float)
    y_valid = y_valid.astype(float)
    
    print(f"Running Logistic Regression on {len(X_valid)} valid samples...")
    
    # Fit the Model
    model = sm.Logit(y_valid, X_valid)
    result = model.fit(disp=False)
    
    return result

def generate_report():
    print("1) Loading Base Dataset for Logistic Regression...")
    with open('rq1_deepseek_filtered.json', 'r') as f:
        raw_data = json.load(f)
        
    rows = []
    for pr in raw_data:
        row = pr.copy()
        
        # Outcome Definition
        row['success'] = 1 if pr.get('resolution_time_seconds') is not None else 0
        
        # Extracted RQ1 Vars
        test_loc = pr.get('test_additions', 0) + pr.get('test_deletions', 0)
        prod_loc = pr.get('prod_additions', 0) + pr.get('prod_deletions', 0)
        
        if prod_loc == 0:
            row['raw_test_to_code_ratio'] = np.nan if test_loc == 0 else 10.0
        else:
            row['raw_test_to_code_ratio'] = min(test_loc / prod_loc, 10.0)
            
        row['log_stars'] = np.log1p(pr.get('project_stars', 0))
        rows.append(row)
        
    df = pd.DataFrame(rows)
    print(f"Base Dataset loaded with {len(df)} records.")

    # Execute Logistic Regression
    logit_res = run_logistic_regression(df)
    
    print("2) Loading Hallucination Dataset (Failed PRs)...")
    hallucination_df = None
    if os.path.exists('rq2_hallucination_dataset.json'):
        with open('rq2_hallucination_dataset.json', 'r') as f:
            h_data = json.load(f)
            hallucination_df = pd.DataFrame(h_data)
        print(f"Loaded {len(hallucination_df)} Failed PRs for DeepSeek Chat analysis.")
    else:
        print("Warning: rq2_hallucination_dataset.json not found. Did the extraction script finish?")

    print("3) Compiling RQ2 Markdown Report...")
    # Markdown Compilation
    os.makedirs('figures', exist_ok=True)
    md = []
    
    md.append("# RQ2: Agent Reliability and Merge Outcomes\n")
    md.append("This report examines how an agent's **testing behavior** correlates with human PR acceptance, and evaluates the textual **reliability** of agents when PRs fail.\n")
    
    md.append("## 1. Predictive Modeling: What drives Merge Success?\n")
    md.append("To determine the isolated impact of testing behaviors on the exact binary PR outcome (`Merged` vs `Failed`), we executed a **Multivariate Logistic Regression Model**.\n")
    md.append("- **Dependent Variable**: PR Success (`1` = Merged, `0` = Closed/Unmerged).\n")
    md.append("- **Independent Variables**: Test-to-Code Ratio, Trial-and-Error Commits, Repo Size (Log Stars), and Dominant Test Type (baseline: Unit).\n")
    
    md.append("\n### Logistic Regression Outcomes\n")
    md.append("| Variable | Odds Ratio (Exp[Coeff]) | p-value | Interpretation |\n")
    md.append("|---|---|---|---|\n")
    
    for var, coef in logit_res.params.items():
        if var == 'const':
            continue
        p_val = logit_res.pvalues[var]
        odds_ratio = np.exp(coef)
        
        sign = "Increases" if odds_ratio > 1 else "Decreases"
        percentage = abs(odds_ratio - 1) * 100
        interp = f"{sign} merge odds by {percentage:.1f}% per unit"
        if var in ['e2e', 'integration']:
             interp = f"{sign} merge odds by {percentage:.1f}% compared to Unit Tests"
             
        # Significance bolding
        bold_p = f"**{p_val:.4g}**" if p_val < 0.05 else f"{p_val:.4g}"
        
        md.append(f"| `{var}` | {odds_ratio:.4f} | {bold_p} | {interp} |\n")
        
    md.append(f"\n*Note: Model computed on {int(logit_res.nobs)} valid records. P-values < 0.05 are statistically significant. Pseudo R-squared: {logit_res.prsquared:.4f}.*\n")
    
    md.append("---\n")
    
    md.append("## 2. Agent Hallucinations (Analysis of Failed PRs)\n")
    if hallucination_df is not None and not hallucination_df.empty:
        md.append("For the PRs that were strictly **rejected/failed**, we processed their conversational Markdown histories through **DeepSeek-V3.2** to detect False Positive Claims (Hallucinations).\n")
        
        total_failed = len(hallucination_df)
        
        hallucination_df['agent_claimed_success'] = hallucination_df['agent_claimed_success'].fillna(False).astype(bool)
        hallucination_df['reviewer_refuted'] = hallucination_df['reviewer_refuted'].fillna(False).astype(bool)
        
        claimed = hallucination_df['agent_claimed_success'].sum()
        refuted = hallucination_df['reviewer_refuted'].sum()
        both = hallucination_df[(hallucination_df['agent_claimed_success'] == True) & (hallucination_df['reviewer_refuted'] == True)].shape[0]
        
        md.append("### Conversation Metrics\n")
        md.append(f"- **Total Failed PRs Analyzed**: {total_failed}\n")
        md.append(f"- **Agent Claimed Success**: In **{claimed}** PRs ({claimed/total_failed*100:.1f}%), the autonomous agent explicitly stated in the comments/body that its tests completely passed or executed perfectly despite the PR ultimately failing.\n")
        md.append(f"- **Reviewer Refutation**: In **{refuted}** PRs ({refuted/total_failed*100:.1f}%), the human reviewer explicitly pointed out that the tests were broken, the CI failed, or the agent's logic was functionally incorrect.\n")
        if claimed > 0:
            md.append(f"- **Direct Confrontation**: Of the {claimed} instances where the agent bragged about success, human reviewers strictly rebutted them **{both}** times ({both/claimed*100:.1f}%).\n")
            
        md.append("\n### Hallucinations by Agent Vendor\n")
        md.append("| Agent | Failed PRs | Hallucinated Pass Claims | Hallucination Rate |\n")
        md.append("|---|---|---|---|\n")
        
        groups = hallucination_df.groupby('agent_type')
        for vendor, group in groups:
            n_failed = len(group)
            n_claimed = group['agent_claimed_success'].sum()
            rate = n_claimed / n_failed * 100 if n_failed > 0 else 0
            md.append(f"| **{vendor}** | {n_failed} | {n_claimed} | {rate:.1f}% |\n")
            
        # Generates a Bar Chart
        plt.figure(figsize=(10, 6))
        
        plot_df = hallucination_df.groupby('agent_type')['agent_claimed_success'].mean().reset_index()
        plot_df['agent_claimed_success'] *= 100 # percentage
        plot_df = plot_df.sort_values(by='agent_claimed_success', ascending=False)
        
        sns.barplot(data=plot_df, x='agent_type', y='agent_claimed_success', palette='Reds_r')
        plt.title('Agent Hallucination Rate (False Claims of Success in Failed PRs)')
        plt.ylabel('% of Failed PRs with Hallucinated Claims')
        plt.xlabel('Agent Vendor')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig('figures/rq2_hallucination_vendor.png')
        plt.close()
        
        md.append("\n![Agent Hallucination Rate](figures/rq2_hallucination_vendor.png)\n")
        
        md.append("\n![Agent Hallucination Rate](figures/rq2_hallucination_vendor.png)\n")
        
    else:
        md.append("> *DeepSeek chat payload is still processing failed PRs. Check back later!*\n")

    print("4) Loading Success Claims Dataset (Merged PRs)...")
    success_claims_df = None
    if os.path.exists('rq2_hallucination_dataset_success.json'):
        with open('rq2_hallucination_dataset_success.json', 'r') as f:
            sc_data = json.load(f)
            success_claims_df = pd.DataFrame(sc_data)
        print(f"Loaded {len(success_claims_df)} Merged PRs for DeepSeek Chat analysis.")
        
    md.append("---\n")
    md.append("## 3. Agent Claims (Analysis of Merged PRs)\n")
    
    if success_claims_df is not None and not success_claims_df.empty:
        md.append("For the PRs that successfully **merged**, we processed their conversational Markdown histories through **DeepSeek-V3.2** to analyze their testing claims during the review process.\n")
        
        total_merged = len(success_claims_df)
        
        success_claims_df['agent_claimed_success'] = success_claims_df['agent_claimed_success'].fillna(False).astype(bool)
        success_claims_df['reviewer_refuted'] = success_claims_df['reviewer_refuted'].fillna(False).astype(bool)
        
        claimed = success_claims_df['agent_claimed_success'].sum()
        refuted = success_claims_df['reviewer_refuted'].sum()
        both = success_claims_df[(success_claims_df['agent_claimed_success'] == True) & (success_claims_df['reviewer_refuted'] == True)].shape[0]
        
        md.append("### Conversation Metrics for Successful PRs\n")
        md.append(f"- **Total Merged PRs Analyzed**: {total_merged}\n")
        md.append(f"- **Agent Claimed Success**: In **{claimed}** PRs ({claimed/total_merged*100:.1f}%), the autonomous agent explicitly stated in the comments/body that its tests completely passed or executed perfectly.\n")
        md.append(f"- **Reviewer Refutation**: In **{refuted}** PRs ({refuted/total_merged*100:.1f}%), despite the PR eventually merging, the human reviewer explicitly pointed out initial bugs, failing CI, or issues with the tests.\n")
        if claimed > 0:
            md.append(f"- **Initial Pushback**: Of the {claimed} instances where the agent bragged about success, human reviewers strictly rebutted them **{both}** times ({both/claimed*100:.1f}%) before eventually accepting the code.\n")
            
        md.append("\n### Claims by Agent Vendor (Successful PRs)\n")
        md.append("| Agent | Merged PRs | Valid Pass Claims | Claim Rate |\n")
        md.append("|---|---|---|---|\n")
        
        groups = success_claims_df.groupby('agent_type')
        for vendor, group in groups:
            n_merged = len(group)
            n_claimed = group['agent_claimed_success'].sum()
            rate = n_claimed / n_merged * 100 if n_merged > 0 else 0
            md.append(f"| **{vendor}** | {n_merged} | {n_claimed} | {rate:.1f}% |\n")
            
        # Generates a Bar Chart
        plt.figure(figsize=(10, 6))
        
        plot_df2 = success_claims_df.groupby('agent_type')['agent_claimed_success'].mean().reset_index()
        plot_df2['agent_claimed_success'] *= 100 # percentage
        plot_df2 = plot_df2.sort_values(by='agent_claimed_success', ascending=False)
        
        sns.barplot(data=plot_df2, x='agent_type', y='agent_claimed_success', hue='agent_type', palette='Greens_r', legend=False)
        plt.title('Agent Claim Rate (Explicit Claims of Success in Merged PRs)')
        plt.ylabel('% of Merged PRs with Success Claims')
        plt.xlabel('Agent Vendor')
        plt.xticks(rotation=45)
        plt.tight_layout()
        plt.savefig('figures/rq2_claims_vendor_success.png')
        plt.close()
        
        md.append("\n![Agent Claim Rate - Merged](figures/rq2_claims_vendor_success.png)\n")
        
    else:
        md.append("> *DeepSeek chat payload is still processing Merged PRs. Check back later!*\n")
        
    with open('rq2_analysis_report.md', 'w') as f:
        f.write('\n'.join(md))
        
    print("Done! rq2_analysis_report.md and /figures/ generated.")

if __name__ == "__main__":
    generate_report()
