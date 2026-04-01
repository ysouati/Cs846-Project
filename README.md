# Empirical Study of Testing Behavior in Agentic Pull Requests

## Abstract
AI coding agents such as GitHub Copilot, Devin, Cursor, Claude Code, and OpenAI Codex now autonomously open pull requests, respond to reviews, and run tests. Yet little empirical work has examined how these agents test the code they produce, whether their testing claims are trustworthy, or how their test organization compares to that of human developers. 

We study testing behavior in agentic pull requests using the AIDev dataset (nearly one million PRs across 116,211 repositories). Through regex-based heuristics, LLM-assisted validation with DeepSeek-V3.2, and GitHub API data curation, we isolate **6,366 verified test-bearing PRs** and analyze them along three dimensions: 
1. Test type distribution, trial-and-error debugging patterns, and CI failure resolution.
2. The link between testing behavior and merge outcomes, including a hallucination analysis of false test-success claims.
3. Test locality, comparing directory distance between test and production files for agents versus humans. 

We find that agents produce mostly unit tests, achieve a median test-to-code ratio above 1.0, and merge at high rates on single-commit PRs but struggle with multi-commit debugging. We identify 221 PRs where agents falsely claimed test success, with human reviewers rebutting 52 of these claims. Agents also place tests significantly closer to production code than humans (42.9% co-located vs. 0.85%), suggesting weaker adherence to repository conventions. These results have direct implications for code review workflows and CI pipeline design.

---

## 1. Introduction
The landscape of software development has been transformed by the emergence of large language model (LLM)-powered coding agents. Tools such as GitHub Copilot, OpenAI Codex, Devin, Cursor, and Claude Code have progressed far beyond inline code suggestions; they now autonomously open pull requests, respond to code review comments, run test suites, and iteratively debug failing CI pipelines. This paradigm shift, from passive assistants to active project contributors—or what is termed *AI teammates in the era of SE 3.0*—raises questions about the quality, reliability, and trustworthiness of agent-produced software artifacts.

Software testing occupies a central role in this discussion. Testing is the primary mechanism through which developers and reviewers gain confidence that a code change is correct, does not introduce regressions, and integrates well with the broader system. When a human developer submits a pull request, reviewers can examine the accompanying tests, verify CI pipeline results, and engage in iterative dialogue about edge cases and coverage. When an autonomous agent submits a pull request, the same scrutiny applies in principle, but the dynamics differ. An agent may claim that it has executed tests and that they pass, yet the reviewer has limited visibility into whether the agent’s local execution environment mirrors the project’s CI configuration, whether the agent ran the correct test suite, or whether the claim itself is a hallucination.

Despite the rapid adoption of agentic coding tools in open-source ecosystems, there is a significant gap in empirical understanding of how these agents interact with the testing dimension of software engineering. Prior work has examined agent code quality at a high level, but a detailed, multi-faceted analysis of testing behavior (encompassing test type distribution, test-to-code ratios, CI failure resolution patterns, the reliability of agent self-reports, and test file organization practices) has not been conducted at scale.

This project addresses that gap. We present an empirical study of testing behavior in agentic pull requests, leveraging the **AIDev dataset**, which was featured in the *MSR 2026 Mining Challenge*. 

### Research Questions
Our study is organized around three primary research questions:
- **RQ1**: How do coding agents perform software testing in open-source pull requests, and what project or pull request factors influence this behavior?
- **RQ2**: What is the relationship between agent testing behavior and pull request outcomes, and how reliable are agents’ claims that tests were executed successfully?
- **RQ3**: How local are agent-written tests to the code changes they accompany, and are they different compared to human-authored pull requests?

### Contributions
Our key contributions include: 
1. A rigorous two-phase test identification pipeline combining regex heuristics with LLM-based semantic validation.
2. A characterization of agent testing patterns across five major coding agents.
3. The first systematic analysis of agent hallucination in testing claims.
4. A novel test locality metric comparing agent and human structural practices.