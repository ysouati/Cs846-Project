# Research Question 3: Test Locality Analysis

This report investigates the architectural coupling of test files mapped against their corresponding production code modifiers, asking: *"How local are agent-written tests compared to human-authored tests?"*

## 1. Directory Distance Statistics
Directory Distance represents how many folder traversals are required to reach the common parent namespace spanning a Test file and a Prod file. **Distance 0** implies they map exactly into the same folder block.

| Author Group   |   PR Count |   Average Distance |   Median Distance |   Std Dev | % at Distance 0 (Total Coupling)   |
|:---------------|-----------:|-------------------:|------------------:|----------:|:-----------------------------------|
| Agent          |       7917 |            2.22925 |                 1 |   2.79459 | 42.9%                              |
| Human          |        938 |            3.98348 |                 4 |   2.60438 | 0.85%                              |

## 2. Locality Structural Variances

The visualizations below outline whether fully autonomous agents natively cluster their unit tests in parallel module arrays, or directly couple them beside standard production modules at higher rates than Human baseline cohorts.

![Locality Distribution Chart](figures/rq3_locality_box.png)

![Locality Density Topology](figures/rq3_locality_kde.png)