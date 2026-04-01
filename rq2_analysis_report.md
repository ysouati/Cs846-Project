# RQ2: Agent Reliability and Merge Outcomes

This report examines how an agent's **testing behavior** correlates with human PR acceptance, and evaluates the textual **reliability** of agents when PRs fail.

## 1. Predictive Modeling: What drives Merge Success?

To determine the isolated impact of testing behaviors on the exact binary PR outcome (`Merged` vs `Failed`), we executed a **Multivariate Logistic Regression Model**.

- **Dependent Variable**: PR Success (`1` = Merged, `0` = Closed/Unmerged).

- **Independent Variables**: Test-to-Code Ratio, Trial-and-Error Commits, Repo Size (Log Stars), and Dominant Test Type (baseline: Unit).


### Logistic Regression Outcomes

| Variable | Odds Ratio (Exp[Coeff]) | p-value | Interpretation |

|---|---|---|---|

| `raw_test_to_code_ratio` | 1.0295 | **9.253e-06** | Increases merge odds by 2.9% per unit |

| `trial_and_error_commits` | 0.9778 | **7.71e-11** | Decreases merge odds by 2.2% per unit |

| `log_stars` | 0.6421 | **2.857e-195** | Decreases merge odds by 35.8% per unit |

| `e2e` | 0.7848 | 0.09296 | Decreases merge odds by 21.5% compared to Unit Tests |

| `integration` | 0.8748 | 0.2307 | Decreases merge odds by 12.5% compared to Unit Tests |


*Note: Model computed on 8807 valid records. P-values < 0.05 are statistically significant. Pseudo R-squared: 0.1205.*

---

## 2. Agent Hallucinations (Analysis of Failed PRs)

For the PRs that were strictly **rejected/failed**, we processed their conversational Markdown histories through **DeepSeek-V3.2** to detect False Positive Claims (Hallucinations).

### Conversation Metrics

- **Total Failed PRs Analyzed**: 2651

- **Agent Claimed Success**: In **99** PRs (3.7%), the autonomous agent explicitly stated in the comments/body that its tests completely passed or executed perfectly despite the PR ultimately failing.

- **Reviewer Refutation**: In **173** PRs (6.5%), the human reviewer explicitly pointed out that the tests were broken, the CI failed, or the agent's logic was functionally incorrect.

- **Direct Confrontation**: Of the 99 instances where the agent bragged about success, human reviewers strictly rebutted them **23** times (23.2%).


### Hallucinations by Agent Vendor

| Agent | Failed PRs | Hallucinated Pass Claims | Hallucination Rate |

|---|---|---|---|

| **Claude_Code** | 69 | 4 | 5.8% |

| **Copilot** | 844 | 87 | 10.3% |

| **Cursor** | 89 | 1 | 1.1% |

| **Devin** | 583 | 4 | 0.7% |

| **OpenAI_Codex** | 1066 | 3 | 0.3% |


![Agent Hallucination Rate](figures/rq2_hallucination_vendor.png)


![Agent Hallucination Rate](figures/rq2_hallucination_vendor.png)

---

## 3. Agent Claims (Analysis of Merged PRs)

For the PRs that successfully **merged**, we processed their conversational Markdown histories through **DeepSeek-V3.2** to analyze their testing claims during the review process.

### Conversation Metrics for Successful PRs

- **Total Merged PRs Analyzed**: 6156

- **Agent Claimed Success**: In **122** PRs (2.0%), the autonomous agent explicitly stated in the comments/body that its tests completely passed or executed perfectly.

- **Reviewer Refutation**: In **143** PRs (2.3%), despite the PR eventually merging, the human reviewer explicitly pointed out initial bugs, failing CI, or issues with the tests.

- **Initial Pushback**: Of the 122 instances where the agent bragged about success, human reviewers strictly rebutted them **29** times (23.8%) before eventually accepting the code.


### Claims by Agent Vendor (Successful PRs)

| Agent | Merged PRs | Valid Pass Claims | Claim Rate |

|---|---|---|---|

| **Claude_Code** | 86 | 5 | 5.8% |

| **Copilot** | 629 | 103 | 16.4% |

| **Cursor** | 123 | 0 | 0.0% |

| **Devin** | 322 | 8 | 2.5% |

| **OpenAI_Codex** | 4996 | 6 | 0.1% |


![Agent Claim Rate - Merged](figures/rq2_claims_vendor_success.png)
