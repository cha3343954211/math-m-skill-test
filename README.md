# Math Modeling Skill Test Results

This repository contains real application outputs produced while testing the [`math-modeling` Hermes Agent skill](https://github.com/cha3343954211/math-modeling-skill) on Chinese National Undergraduate Mathematical Contest in Modeling (CUMCM / 国赛) historical problems.

## Purpose

These files demonstrate how the skill behaves on complete mathematical modeling workflows, including:

- problem analysis and modeling route design;
- code implementation and reproducible outputs;
- figures, tables, and frozen result files;
- paper drafts / LaTeX / PDFs where available;
- supporting-material organization for contest-style submission.

## Model Usage Statement

The full test set was produced with mixed use of the following model families across different problems:

- `gpt-5.5`
- `mimo-v2.5`
- `mimo-v2.5-pro`
- `deepseek v4 flash`
- `deepseek v4 pro`
- `glm5.1`

Important constraint: **each individual problem was completed end-to-end with only one model**. Models were mixed across the overall test set, not within a single problem workflow.

## Scope of Included Files

The test artifacts are stored under:

```text
examples/test-results/
```

To keep the Git repository practical, the copy excludes generated caches, Python bytecode, LaTeX intermediates, and duplicate `.zip` packages. See `examples/test-results/copy_manifest.json` for copy statistics and examples of excluded files.

## Notes

- Some problem statements and official format files are historical CUMCM materials used as test inputs.
- The generated supporting materials are intended as examples of workflow output, not as official contest solutions.
- If a PDF, spreadsheet, or image is present, it is kept as part of the test artifact for reproducibility and visual inspection.
