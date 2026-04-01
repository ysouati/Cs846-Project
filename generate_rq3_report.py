import json
import pandas as pd
import numpy as np
import scipy.stats as st
import matplotlib.pyplot as plt
import seaborn as sns
from datasets import load_dataset
import os

def load_data():
    print("Loading RQ1 filtered dataset...")
    with open('rq1_deepseek_filtered.json', 'r') as f:
        pr_data = json.load(f)
        
    df = pd.DataFrame(pr_data)
    
    df['success'] = df['resolution_time_seconds'].notna().astype(int)
    
    test_loc = df['test_additions'].fillna(0) + df['test_deletions'].fillna(0)
    prod_loc = df['prod_additions'].fillna(0) + df['prod_deletions'].fillna(0)
    
    ratio = np.where(prod_loc == 0, 
                     np.where(test_loc == 0, np.nan, 10.0), 
                     np.minimum(test_loc / prod_loc, 10.0))
    df['raw_test_to_code_ratio'] = ratio
    
    print("Loading Repository Language Data from HuggingFace...")
    repo_ds = load_dataset('hao-li/AIDev', 'repository', split='train')
    
    repo_lang_map = {}
    for row in repo_ds:
        if row.get('full_name'):
            lang = row.get('language')
            if lang:
                repo_lang_map[row['full_name']] = lang
                
    df['language'] = df['repo_full_name'].map(repo_lang_map)
    df['language'] = df['language'].fillna('Unknown')
    
    top_langs = df[df['language'] != 'Unknown']['language'].value_counts().nlargest(10).index
    df['top_language'] = df['language'].apply(lambda x: x if x in top_langs else 'Other')
    
    return df, top_langs

def generate_report():
    df, top_langs = load_data()
    os.makedirs('figures', exist_ok=True)
    
    md_content = ["# Language Impact on Agent Testing Behavior\n"]
    md_content.append("This report analyzes how the programming language of the target repository affects the autonomous agent's testing behavior, focusing on test types, success rates, and test-to-code ratios.\n")
    
    df_top = df[df['top_language'] != 'Other']
    
    md_content.append("## 1. Distribution of Test PRs by Language\n")
    lang_counts = df_top['language'].value_counts()
    
    md_content.append("| Language | Test PR Count | % of Total |\n")
    md_content.append("|---|---|---|\n")
    total_prs = len(df_top)
    for lang, count in lang_counts.items():
        md_content.append(f"| {lang} | {count} | {(count/total_prs*100):.1f}% |\n")
    md_content.append("\n")
        
    plt.figure(figsize=(10, 6))
    
    # Use generic compatible seaborn syntax
    sns.countplot(data=df_top, y='language', order=lang_counts.index, palette='crest')
    plt.title("Volume of Agent Testing PRs by Top Languages")
    plt.xlabel("Number of PRs")
    plt.ylabel("Language")
    plt.tight_layout()
    plt.savefig('figures/rq3_language_volume.png')
    plt.close()
    md_content.append("![Volume by Language](figures/rq3_language_volume.png)\n\n")

    md_content.append("## 2. Test-to-Code Ratio by Language\n")
    plt.figure(figsize=(12, 6))
    sns.boxplot(data=df_top, x='language', y='raw_test_to_code_ratio', order=lang_counts.index, palette='Set2')
    plt.title("Test-to-Code Ratio by Programming Language (Capped at 10.0)")
    plt.xlabel("Language")
    plt.ylabel("Test / Production LOC Ratio")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('figures/rq3_language_ratio.png')
    plt.close()
    
    groups = [group['raw_test_to_code_ratio'].dropna().values for name, group in df_top.groupby('language')]
    groups = [g for g in groups if len(g) > 0]
    if len(groups) > 1:
        h_stat, p_kw = st.kruskal(*groups)
        md_content.append(f"A Kruskal-Wallis H-test on the test-to-code ratios across these top languages yielded a **p-value of {p_kw:.4g}** (H = {h_stat:.2f}). ")
        if p_kw < 0.05:
             md_content.append("This indicates a **statistically significant difference** in how verbose agent tests are depending on the programming language.\n")
        else:
             md_content.append("This indicates NO significant difference in agent test verbosity across languages.\n")
    
    md_content.append("\n![Ratio by Language](figures/rq3_language_ratio.png)\n\n")

    md_content.append("## 3. Dominant Test Type by Language\n")
    ct = pd.crosstab(df_top['language'], df_top['dominant_test_type'], normalize='index') * 100
    
    ct.plot(kind='bar', stacked=True, figsize=(10, 6), colormap='viridis')
    plt.title("Proportion of Test Types Written by Agent per Language")
    plt.xlabel("Language")
    plt.ylabel("Percentage (%)")
    plt.legend(title='Test Type', bbox_to_anchor=(1.05, 1), loc='upper left')
    plt.tight_layout()
    plt.savefig('figures/rq3_language_test_type.png')
    plt.close()
    
    md_content.append("Agents may favor different testing strategies (e.g., E2E vs Unit) depending on the ecosystem (e.g., JavaScript vs Python).\n")
    md_content.append("\n![Test Types by Language](figures/rq3_language_test_type.png)\n\n")
    
    ct_raw = pd.crosstab(df_top['language'], df_top['dominant_test_type'])
    chi2, p_chi, dof, ex = st.chi2_contingency(ct_raw)
    md_content.append(f"A Chi-Square test of independence between Language and Dominant Test Type yielded a **p-value of {p_chi:.4g}**. ")
    if p_chi < 0.05:
         md_content.append("This strongly suggests that the **choice of test type is heavily influenced by the repository's programming language**.\n\n")
    else:
         md_content.append("This implies no significant dependency.\n\n")

    md_content.append("## 4. PR Success Rate by Language\n")
    success_rates = df_top.groupby('language')['success'].mean().sort_values(ascending=False) * 100
    
    plt.figure(figsize=(10, 6))
    sns.barplot(x=success_rates.index, y=success_rates.values, palette='RdYlGn')
    plt.title("Agent PR Merge Success Rate by Language")
    plt.xlabel("Language")
    plt.ylabel("Success Rate (%)")
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig('figures/rq3_language_success.png')
    plt.close()
    
    md_content.append("Finally, we evaluate if agents are statistically more successful at getting their PRs merged in specific languages.\n")
    md_content.append("\n![Success Rate by Language](figures/rq3_language_success.png)\n\n")
    
    md_content.append("| Language | Merge Success Rate |\n")
    md_content.append("|---|---|\n")
    for lang, rate in success_rates.items():
        md_content.append(f"| {lang} | {rate:.1f}% |\n")

    with open('rq3_language_report.md', 'w') as f:
        f.write("".join(md_content))
        
    print("Report generated at rq3_language_report.md")

if __name__ == "__main__":
    generate_report()
