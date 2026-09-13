# ASG Evaluation

Shared validation and atomic persistence for human evaluations attached to ASG story
runs. Writes are serialized with `asg_core.file_lock`, so the Telegram bot and the console
can append at the same time without losing an evaluation.

The package also reads: `read_evaluations`, `collect_evaluations` and `summarize` expose
mean and variance per story, narrative profile, generator version, or approach, and the
`report-evaluations` command prints that report and exports one CSV row per evaluation.
