"""Pure metric calculation from final simulation state."""

from .contracts import SimulationMetrics
from .domain import WorldState


def collect_metrics(world: WorldState) -> SimulationMetrics:
    """Collect metrics."""
    agent_metrics = {i: agent.metrics for i, agent in world.characters.items()}
    success = all(agent.escaped for agent in world.characters.values())
    return SimulationMetrics(
        escaped=success,
        ticks=world.tick,
        puzzles_solved=len(world.solved),
        messages_sent=sum(metric.messages for metric in agent_metrics.values()),
        blocked_time=sum(metric.waits for metric in agent_metrics.values()),
        invalid_actions=sum(metric.invalid_actions for metric in agent_metrics.values()),
        agents=agent_metrics,
    )
