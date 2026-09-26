"""The performance: actors with their own memory improvise the frozen script, scene by scene.

This is the bottom-up half of the hybrid pipeline. The plan and the script decide what must
happen; nothing here decides that again. What the modules below decide is *how* it happens: who
speaks, what they know when they speak, and what the log of that performance says afterwards.

Everything that is not a model call is pure and deterministic - turn order, perception, memory
retrieval and validation - exactly as in the escape-room simulation, so the same run with the
same responses produces the same log.
"""
