# Language Impact on Agent Testing Behavior
This report analyzes how the programming language of the target repository affects the autonomous agent's testing behavior, focusing on test types, success rates, and test-to-code ratios.
## 1. Distribution of Test PRs by Language
| Language | Test PR Count | % of Total |
|---|---|---|
| Go | 3337 | 40.3% |
| Python | 2250 | 27.2% |
| TypeScript | 909 | 11.0% |
| C# | 610 | 7.4% |
| Java | 492 | 5.9% |
| JavaScript | 184 | 2.2% |
| Rust | 184 | 2.2% |
| C++ | 111 | 1.3% |
| Zig | 110 | 1.3% |
| PHP | 96 | 1.2% |

![Volume by Language](figures/rq3_language_volume.png)

## 2. Test-to-Code Ratio by Language
A Kruskal-Wallis H-test on the test-to-code ratios across these top languages yielded a **p-value of 3.576e-127** (H = 617.55). This indicates a **statistically significant difference** in how verbose agent tests are depending on the programming language.

![Ratio by Language](figures/rq3_language_ratio.png)

## 3. Dominant Test Type by Language
Agents may favor different testing strategies (e.g., E2E vs Unit) depending on the ecosystem (e.g., JavaScript vs Python).

![Test Types by Language](figures/rq3_language_test_type.png)

A Chi-Square test of independence between Language and Dominant Test Type yielded a **p-value of 7.657e-70**. This strongly suggests that the **choice of test type is heavily influenced by the repository's programming language**.

## 4. PR Success Rate by Language
Finally, we evaluate if agents are statistically more successful at getting their PRs merged in specific languages.

![Success Rate by Language](figures/rq3_language_success.png)

| Language | Merge Success Rate |
|---|---|
| Go | 84.1% |
| Java | 70.9% |
| Python | 70.0% |
| JavaScript | 65.8% |
| PHP | 63.5% |
| Rust | 53.8% |
| TypeScript | 51.3% |
| C# | 49.5% |
| C++ | 36.0% |
| Zig | 28.2% |
