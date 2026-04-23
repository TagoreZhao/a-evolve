"""`EvolvableTerminus2` — stock Harbor Terminus-2 extended to upload the
a-evolve workspace's local `skills/` directory into the container at setup
time, so `Terminus2._build_skills_section()` can discover SKILL.md files.

Loaded by Harbor in the metaharness Python env via the config's
`import_path: agent_evolve.agents.terminus_2.evolvable:EvolvableTerminus2`.

This file intentionally imports only from stdlib and `harbor.*`, so it loads
cleanly in Python 3.13 (metaharness) regardless of a-evolve's Python 3.11.
Nothing outside this file references a-evolve symbols — Harbor just needs
the class to be importable given the right PYTHONPATH.
"""

from __future__ import annotations

import logging
import os
import shlex
from pathlib import Path

from harbor.agents.terminus_2 import Terminus2
from harbor.environments.base import BaseEnvironment

logger = logging.getLogger(__name__)


class EvolvableTerminus2(Terminus2):
    """Stock Terminus-2 + staged local skills from a-evolve workspace.

    If the env var ``AEVOLVE_LOCAL_SKILLS_DIR`` is set and contains at least
    one ``<name>/SKILL.md`` file, its contents are uploaded into the
    container at ``self.skills_dir`` before the agent runs. Harbor's own
    ``_build_skills_section()`` (Terminus-2 line 414) then discovers them
    via a container-side ``find`` and injects an ``<available_skills>``
    XML block into the initial instruction.
    """

    @staticmethod
    def name() -> str:
        return "evolvable-terminus-2"

    async def setup(self, environment: BaseEnvironment) -> None:
        # Parent handles the tmux session and terminal recording setup.
        await super().setup(environment)

        local_skills = os.environ.get("AEVOLVE_LOCAL_SKILLS_DIR")
        remote_skills = self.skills_dir
        if not local_skills or not remote_skills:
            return

        local_path = Path(local_skills)
        if not local_path.is_dir():
            logger.info("AEVOLVE_LOCAL_SKILLS_DIR=%s is not a dir; skipping skills upload", local_skills)
            return

        has_any = any(
            (local_path / d / "SKILL.md").is_file()
            for d in os.listdir(local_path)
            if (local_path / d).is_dir()
        )
        if not has_any:
            logger.info("No SKILL.md files under %s; skipping skills upload", local_skills)
            return

        logger.info("Uploading a-evolve skills %s -> container:%s", local_path, remote_skills)
        await environment.exec(f"mkdir -p {shlex.quote(remote_skills)}")
        await environment.upload_dir(str(local_path), remote_skills)
