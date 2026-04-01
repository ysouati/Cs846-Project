import json
import os
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt

def main():
    print("1) Loading RQ3 Locality Dataset...")
    try:
        with open("rq3_locality_dataset.json", "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        print("Error: Could not find rq3_locality_dataset.json")
        return
        
    df = pd.DataFrame(data)
    
    # Filter out empty metrics defensively
    df = df[df['median_locality_distance'].notnull()]
    
    # We enforce a generic 'Agent' vs 'Human' paradigm, collapsing detailed agent names into Agent
    df['Author Group'] = df['author_type'].apply(lambda x: 'Human' if x.lower() == 'human' else 'Agent')
    
    # Pre-calculate grouped summary statistics for the Markdown export
    stats_df = df.groupby('Author Group')['median_locality_distance'].agg(['count', 'mean', 'median', 'std']).reset_index()
    stats_df.rename(columns={'count': 'PR Count', 'mean': 'Average Distance', 'median': 'Median Distance', 'std': 'Std Dev'}, inplace=True)
    
    # Breakdown at 0 distance % vs further distance %
    zero_dist_counts = df[df['median_locality_distance'] == 0].groupby('Author Group').size()
    total_counts = df.groupby('Author Group').size()
    
    zero_dist_pct = (zero_dist_counts / total_counts * 100).fillna(0).round(2)
    stats_df['% at Distance 0 (Total Coupling)'] = stats_df['Author Group'].map(zero_dist_pct).astype(str) + '%'
    
    print("2) Generating Seaborn Visualizations in /figures...")
    os.makedirs("figures", exist_ok=True)
    
    # Set plotting aesthetics
    sns.set_theme(style="whitegrid", context="talk")
    
    # 1. Boxplot comparing the distributions
    plt.figure(figsize=(10, 6))
    ax1 = sns.boxplot(x='Author Group', y='median_locality_distance', data=df, palette='Set2', showfliers=False)
    plt.title("Test Locality Distribution (Agent vs Human Authors)", fontsize=16)
    plt.ylabel("Median Directory Distance")
    plt.xlabel("Author Category")
    plt.tight_layout()
    plt.savefig("figures/rq3_locality_box.png", dpi=300)
    plt.close()
    
    # 2. KDE Density Plot to display structural separation shapes
    plt.figure(figsize=(10, 6))
    sns.kdeplot(data=df, x='median_locality_distance', hue='Author Group', common_norm=False, fill=True, palette='Set2', clip=(0, 10))
    plt.title("Density Map of Test Directory Distances", fontsize=16)
    plt.xlabel("Directory Levels Away from Prod Source")
    plt.ylabel("Density")
    plt.legend(title='Author Group', labels=['Agent', 'Human'])
    plt.tight_layout()
    plt.savefig("figures/rq3_locality_kde.png", dpi=300)
    plt.close()
    
    print("3) Writing rq3_analysis_report.md...")
    md = [
        "# Research Question 3: Test Locality Analysis",
        "\nThis report investigates the architectural coupling of test files mapped against their corresponding production code modifiers, asking: *\"How local are agent-written tests compared to human-authored tests?\"*",
        "\n## 1. Directory Distance Statistics",
        "Directory Distance represents how many folder traversals are required to reach the common parent namespace spanning a Test file and a Prod file. **Distance 0** implies they map exactly into the same folder block.\n",
        stats_df.to_markdown(index=False),
        "\n## 2. Locality Structural Variances",
        "\nThe visualizations below outline whether fully autonomous agents natively cluster their unit tests in parallel module arrays, or directly couple them beside standard production modules at higher rates than Human baseline cohorts.",
        "\n![Locality Distribution Chart](figures/rq3_locality_box.png)",
        "\n![Locality Density Topology](figures/rq3_locality_kde.png)"
    ]
    
    with open("rq3_analysis_report.md", "w") as f:
        f.write("\n".join(md))
        
    print("4) Success. Rendered rq3_analysis_report.md")

if __name__ == "__main__":
    main()
