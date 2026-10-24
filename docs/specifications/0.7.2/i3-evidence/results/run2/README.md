# Run 2 outputs

These are the simulator's outputs, unedited. Read them with the [comparison record](../../../i3-comparison-record.md).

**Not valid:** the quality score (10/100 in both arms) and the diff stat (0 files) in `report.html`, `result.json` and `simulator.log`. Both agents committed their changes, and the simulator only reads uncommitted ones, so the evaluator scored empty diffs. The agents' commits are in `arm-a-commits.patch` (Unblocked only) and `arm-b-commits.patch` (Unblocked + AIP).

**Valid:** every step's output, the transcripts (`transcripts.tar.gz`), the recorded `system/init` events, and the time, token and cost figures.
