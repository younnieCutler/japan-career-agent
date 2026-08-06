# P1 executable workflows

This pack is the executable specification for the three PR2 scenarios. Every run uses a fresh
temporary directory and synthetic fixtures only.

Run all workflows from the repository root:

```bash
python scripts/run_workflows.py --workflow all --format human
```

The runner calls the canonical Career Agent and matching commands, then checks semantic invariants.
It does not enable guided mode, submit an application, send a message, or create a recommendation.

The three workflows are intentionally fixed:

1. [First 10 Minutes](first-10-minutes/README.md)
2. [Real Application](real-application/README.md)
3. [Recovery](recovery/README.md)
