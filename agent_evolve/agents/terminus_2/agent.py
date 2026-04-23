"""`HarborTerminus2Agent` — subprocess driver that lets a-evolve evolve
Harbor's stock Terminus-2 agent.

Flow per `solve(task)`:
  1. Stage the workspace prompt into Harbor's bundled template file
     (backup + restore on process exit).
  2. Render a Harbor config mirroring the user's `terminus2_smoke.yaml`
     exactly, except the agent's `import_path` points at our
     `EvolvableTerminus2` subclass (which uploads workspace skills into
     the container) and `kwargs.extra_env` propagates the local skills dir.
  3. Spawn `harbor run --config <cfg> -y` in the metaharness Python env.
  4. Parse `<jobs_dir>/<job_name>/<trial-*>/result.json` +
     `.../agent/trajectory.json` and return a `Trajectory`.

The evolver is unchanged — it mutates `prompts/system.md` and
`skills/*/SKILL.md` in the workspace between batches. This file just
makes Harbor read those files on the next batch.
"""

from __future__ import annotations

import atexit
import json
import logging
import os
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ...protocol.base_agent import BaseAgent
from ...types import Task, Trajectory

logger = logging.getLogger(__name__)

# Defaults derived from the user's environment.
DEFAULT_HARBOR_CLI = "/home/gost/miniconda3/envs/metaharness/bin/harbor"
DEFAULT_HARBOR_TEMPLATE = (
    "/home/gost/miniconda3/envs/metaharness/lib/python3.13/site-packages/"
    "harbor/agents/terminus_2/templates/terminus-json-plain.txt"
)
DEFAULT_META_HARNESS_DIR = "/home/gost/repo/meta-harness"


_BACKUP_SUFFIX = ".aevolve-orig"
_restore_registered = False
_backups_to_restore: list[tuple[Path, Path]] = []


def _register_prompt_restore(template_path: Path) -> None:
    """Back up Harbor's bundled prompt template on first use and register
    an atexit handler to restore it when the a-evolve process exits."""
    global _restore_registered

    backup = template_path.with_name(template_path.name + _BACKUP_SUFFIX)
    if not backup.exists():
        if not template_path.exists():
            raise FileNotFoundError(
                f"Harbor prompt template not found: {template_path}. "
                "Set --harbor-template-path or verify the metaharness env."
            )
        shutil.copy2(template_path, backup)
        logger.info("Backed up Harbor prompt: %s -> %s", template_path, backup)

    if (template_path, backup) not in _backups_to_restore:
        _backups_to_restore.append((template_path, backup))

    if not _restore_registered:
        atexit.register(_restore_all_prompts)
        _restore_registered = True


def _restore_all_prompts() -> None:
    for template_path, backup in _backups_to_restore:
        try:
            if backup.exists():
                shutil.copy2(backup, template_path)
                logger.info("Restored Harbor prompt from %s", backup)
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to restore %s: %s", template_path, exc)


@dataclass
class HarborTerminus2Config:
    solver_model: str
    solver_base_url: str
    solver_api_key: str = "dummy"
    harbor_cli: str = DEFAULT_HARBOR_CLI
    harbor_template_path: str = DEFAULT_HARBOR_TEMPLATE
    meta_harness_dir: str = DEFAULT_META_HARNESS_DIR
    jobs_dir: str = "/tmp/aevolve_harbor_jobs"
    log_archive_dir: str | None = None  # If set, each trial dir is copied here.
    per_task_timeout_sec: float = 3600.0
    override_timeout_sec: float = 600.0
    agent_timeout_multiplier: float = 3.0
    force_build: bool = False
    env_file: str | None = None  # Forwarded to `harbor run --env-file`.


class HarborTerminus2Agent(BaseAgent):
    """a-evolve solver that drives Harbor's stock Terminus-2 via subprocess."""

    def __init__(
        self,
        workspace_dir: str | Path,
        *,
        config: HarborTerminus2Config,
    ) -> None:
        super().__init__(workspace_dir)
        self.cfg = config
        self._template_path = Path(config.harbor_template_path)
        self._repo_root = Path(__file__).resolve().parents[3]
        Path(config.jobs_dir).mkdir(parents=True, exist_ok=True)
        if config.log_archive_dir:
            Path(config.log_archive_dir).mkdir(parents=True, exist_ok=True)

    # ── solve ────────────────────────────────────────────────────────

    def solve(self, task: Task) -> Trajectory:
        self._stage_prompt()
        cfg_path, job_dir = self._write_harbor_config(task)
        t0 = time.time()
        try:
            stdout, stderr, rc = self._spawn_harbor(cfg_path)
        except subprocess.TimeoutExpired as exc:
            logger.error("Harbor run timed out after %ss for task %s", exc.timeout, task.id)
            return self._make_error_trajectory(task, f"TIMEOUT after {exc.timeout}s", elapsed=time.time() - t0)
        except Exception as exc:  # pragma: no cover
            logger.error("Harbor run failed for %s: %s", task.id, exc)
            return self._make_error_trajectory(task, f"ERROR: {exc}", elapsed=time.time() - t0)

        elapsed = time.time() - t0

        trial_dir = self._find_trial_dir(job_dir, task.id)
        if trial_dir is None:
            logger.error(
                "No trial dir under %s after harbor run (rc=%s). stderr tail:\n%s",
                job_dir, rc, stderr[-2000:] if stderr else "",
            )
            return self._make_error_trajectory(
                task,
                f"harbor exited rc={rc}; no trial dir found under {job_dir}",
                elapsed=elapsed,
            )

        passed, score, eval_output, usage, conversation = self._parse_trial(trial_dir)

        archived = self._archive_trial(trial_dir, task.id)

        return Trajectory(
            task_id=task.id,
            output=eval_output,
            steps=[{
                "passed": passed,
                "score": score,
                "eval_output": eval_output,
                "harbor_trial_dir": str(trial_dir),
                "harbor_archive_dir": str(archived) if archived else None,
                "harbor_stdout_tail": (stdout or "")[-2000:],
                "harbor_stderr_tail": (stderr or "")[-2000:],
                "harbor_rc": rc,
                "elapsed_sec": elapsed,
                "usage": usage,
            }],
            conversation=conversation,
        )

    # ── prompt staging ───────────────────────────────────────────────

    def _stage_prompt(self) -> None:
        _register_prompt_restore(self._template_path)
        ws_prompt = self.workspace.root / "prompts" / "system.md"
        if not ws_prompt.exists():
            raise FileNotFoundError(f"Workspace prompt missing: {ws_prompt}")
        self._template_path.write_text(ws_prompt.read_text())
        logger.info("Staged workspace prompt (%d chars) -> %s",
                    len(self.system_prompt or ""), self._template_path)

    # ── harbor config + subprocess ────────────────────────────────────

    def _write_harbor_config(self, task: Task) -> tuple[Path, Path]:
        job_name = f"aevolve-{task.id}-{os.getpid()}-{int(time.time())}"
        job_dir = Path(self.cfg.jobs_dir) / job_name
        local_skills = str((self.workspace.root / "skills").resolve())

        config = {
            "job_name": job_name,
            "jobs_dir": str(Path(self.cfg.jobs_dir).resolve()),
            "n_concurrent_trials": 1,
            "agent_timeout_multiplier": self.cfg.agent_timeout_multiplier,
            "environment": {"force_build": bool(self.cfg.force_build)},
            "agents": [{
                "import_path": "agent_evolve.agents.terminus_2.evolvable:EvolvableTerminus2",
                "model_name": f"hosted_vllm/{self.cfg.solver_model}",
                "override_timeout_sec": self.cfg.override_timeout_sec,
                "kwargs": {
                    "api_base": self.cfg.solver_base_url,
                    "temperature": 0.1,
                    "proactive_summarization_threshold": 32000,
                    "model_info": {
                        "max_input_tokens": 253952,
                        "max_output_tokens": 8192,
                        "input_cost_per_token": 0,
                        "output_cost_per_token": 0,
                    },
                    "llm_kwargs": {"request_timeout": 600, "num_retries": 1},
                    "llm_call_kwargs": {
                        "extra_body": {
                            "chat_template_kwargs": {"force_nonempty_content": True}
                        }
                    },
                    "skills_dir": "/aevolve-skills",
                    # NOTE: AEVOLVE_LOCAL_SKILLS_DIR is passed via the subprocess env
                    # in _spawn_harbor(), not via kwargs.extra_env. Harbor's factory
                    # (factory.py:150-158) explicitly passes extra_env=config.env to
                    # create_agent_from_import_path, so putting it inside kwargs would
                    # collide (TypeError: multiple values for 'extra_env'). Also,
                    # Terminus-2's extra_env only plumbs to the tmux session, not the
                    # agent Python process where EvolvableTerminus2.setup() runs.
                },
            }],
            "datasets": [{
                "name": "terminal-bench/terminal-bench-2",
                "task_names": [f"terminal-bench/{task.id}"],
            }],
        }

        cfg_dir = Path(self.cfg.jobs_dir) / "configs"
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_path = cfg_dir / f"{job_name}.yaml"
        cfg_path.write_text(yaml.safe_dump(config, sort_keys=False))
        return cfg_path, job_dir

    def _spawn_harbor(self, cfg_path: Path) -> tuple[str, str, int]:
        env = os.environ.copy()
        env["PYTHONPATH"] = ":".join(filter(None, [
            str(self._repo_root),
            self.cfg.meta_harness_dir,
            env.get("PYTHONPATH", ""),
        ]))
        env["OPENAI_API_KEY"] = self.cfg.solver_api_key
        env["AEVOLVE_LOCAL_SKILLS_DIR"] = str((self.workspace.root / "skills").resolve())

        cmd = [self.cfg.harbor_cli, "run", "--config", str(cfg_path), "-y"]
        if self.cfg.env_file:
            cmd += ["--env-file", self.cfg.env_file]
        logger.info("Spawning: %s (PYTHONPATH first 2 entries: %s, %s)",
                    " ".join(cmd), self._repo_root, self.cfg.meta_harness_dir)

        proc = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            timeout=self.cfg.per_task_timeout_sec,
        )
        return proc.stdout or "", proc.stderr or "", proc.returncode

    # ── result parsing ───────────────────────────────────────────────

    @staticmethod
    def _find_trial_dir(job_dir: Path, task_id: str) -> Path | None:
        if not job_dir.is_dir():
            return None
        candidates = [p for p in job_dir.iterdir()
                      if p.is_dir() and p.name.startswith(f"{task_id}__")]
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.stat().st_mtime)

    @staticmethod
    def _parse_trial(trial_dir: Path) -> tuple[bool, float, str, dict, list[dict]]:
        result_path = trial_dir / "result.json"
        if not result_path.exists():
            return False, 0.0, f"result.json missing under {trial_dir}", {}, []

        result = json.loads(result_path.read_text())
        verifier = (result.get("verifier_result") or {}).get("rewards") or {}
        score = float(verifier.get("reward", 0.0))
        passed = score > 0.0

        agent_result = result.get("agent_result") or {}
        meta = agent_result.get("metadata") or {}
        usage = {
            "input_tokens": agent_result.get("n_input_tokens"),
            "output_tokens": agent_result.get("n_output_tokens"),
            "cache_tokens": agent_result.get("n_cache_tokens"),
            "n_episodes": meta.get("n_episodes"),
            "summarization_count": meta.get("summarization_count"),
        }

        exception_info = result.get("exception_info")
        eval_output_lines = [
            f"task={result.get('task_name')}",
            f"trial={result.get('trial_name')}",
            f"score={score}",
            f"episodes={meta.get('n_episodes')}",
        ]
        if exception_info:
            eval_output_lines.append(f"exception={json.dumps(exception_info)[:500]}")
        eval_output = "\n".join(eval_output_lines)

        conversation: list[dict] = []
        traj_path = trial_dir / "agent" / "trajectory.json"
        if traj_path.exists():
            try:
                traj = json.loads(traj_path.read_text())
                steps = traj.get("steps") if isinstance(traj, dict) else traj
                if isinstance(steps, list):
                    conversation = [s for s in steps if isinstance(s, dict)]
            except Exception as exc:  # pragma: no cover
                logger.warning("Failed to parse trajectory.json: %s", exc)

        return passed, score, eval_output, usage, conversation

    def _archive_trial(self, trial_dir: Path, task_id: str) -> Path | None:
        if not self.cfg.log_archive_dir:
            return None
        dest = Path(self.cfg.log_archive_dir) / task_id / "harbor"
        try:
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(trial_dir, dest)
            return dest
        except Exception as exc:  # pragma: no cover
            logger.warning("Failed to archive trial to %s: %s", dest, exc)
            return None

    @staticmethod
    def _make_error_trajectory(task: Task, msg: str, elapsed: float) -> Trajectory:
        return Trajectory(
            task_id=task.id,
            output=msg,
            steps=[{
                "passed": False,
                "score": 0.0,
                "eval_output": msg,
                "elapsed_sec": elapsed,
                "error": True,
            }],
            conversation=[],
        )
