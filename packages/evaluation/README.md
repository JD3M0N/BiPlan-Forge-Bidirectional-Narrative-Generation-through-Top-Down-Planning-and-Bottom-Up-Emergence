# ASG Evaluation

Shared validation and atomic persistence for human evaluations attached to ASG story
runs. Writes are serialized with `asg_core.file_lock`, so the Telegram bot and the console
can append at the same time without losing an evaluation.

The package also reads: `read_evaluations`, `collect_evaluations` and `summarize` expose
mean and variance per story, narrative profile, generator version, or approach, and the
`report-evaluations` command prints that report and exports one CSV row per evaluation.

Automatic figures live beside the human ones: `collect_story_craft` recomputes the
prose craft of every stored story with `asg_core.craft_metrics`, pairs it with the plan,
review, usage and metadata artifacts of its run, and the `report-story-craft` command
prints median and range per generator version or narrative profile and exports one CSV
row per story. It recomputes from `story.md`, so runs written before the figures existed
are comparable with the ones that record them.
