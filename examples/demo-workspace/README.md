# Synthetic demo workspace

This directory contains no real candidate, company, or job-posting data. It is a safe fixture for
seeing the evidence-based v3 output immediately after installation.

From the repository root, run:

```bash
python _shared/matching_v3.py examples/demo-workspace/matching-input.example.json --text
```

The report intentionally shows an `Unknown` eligibility item, a required skill `Missing` item, and
a confirmed hard `Conflict`. Candidate interest is printed separately and does not change the
objective diagnosis. The optional MHLW reference dataset is not required for this example.

The files under `data/` are a synthetic workspace projection only. They are not a production
pipeline and must not be treated as evidence about a real person or company.
