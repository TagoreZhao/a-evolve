"""Harbor Terminus-2 adapter — runs Harbor's stock Terminus-2 agent as the
a-evolve solver so the evo-0 baseline matches the user's Harbor benchmark.

The agent lives in a different Python env (`/home/gost/miniconda3/envs/metaharness`)
to avoid litellm version conflicts with a-evolve. We drive it via subprocess.
"""

from .agent import HarborTerminus2Agent

__all__ = ["HarborTerminus2Agent"]
