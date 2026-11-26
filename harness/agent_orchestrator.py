"""Supervise local agent CLIs without invoking a shell."""
from __future__ import annotations

import asyncio
import json
from datetime import datetime
import os
from pathlib import Path
import re
import shutil
import signal
import time
from typing import Optional
import uuid

from core.secret_env import sanitized_subprocess_env
from orchestration.personas import PERSONAS, AGENT_FALLBACK_CANDIDATES, get_fallback_candidates
from orchestration.harness2_adapter import Harness2Adapter
from orchestration.executables import installed_executables, installed_path
from orchestration.state_graph import TeamStateGraph, EdgeAction

AGENTS = ('codex', 'claude', 'opencode', 'gemini', 'hermes', 'omp', 'pi', 'crush', 'antigravity', 'api_agent')
TERMINAL = frozenset({'completed', 'failed', 'cancelled', 'timed_out'})

FAILOVER_PATTERNS_QUOTA = (
    re.compile(r"\busage\s+limit\b", re.IGNORECASE),
    re.compile(r"\brate[\s_-]*limit", re.IGNORECASE),
    re.compile(
        r"(?:\b(?:http(?:/[\d.]+)?|status(?:\s+code)?|code|error)\b[^\n\r\d]{0,12}\b429\b"
        r"|\b429\s*[:\-]?\s*(?:too\s+many\s+requests|rate[\s_-]*limit|quota|resource_?exhausted))",
        re.IGNORECASE,
    ),
    re.compile(r"\btoo\s+many\s+requests\b", re.IGNORECASE),
    re.compile(
        r"\b(?:quota\s+exceeded|exceeded\s+your\s+(?:current\s+)?quota|insufficient_quota|out\s+of\s+quota)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bcredit\s+balance\s+is\s+too\s+low\b", re.IGNORECASE),
    re.compile(r"\bresource_?exhausted\b", re.IGNORECASE),
)

FAILOVER_PATTERNS_CONNECTION = (
    re.compile(r"\bECONNREFUSED\b", re.IGNORECASE),
    re.compile(r"\bconnection\s+refused\b", re.IGNORECASE),
    re.compile(r"\bconnecterror\b", re.IGNORECASE),
    re.compile(r"\bfailed\s+to\s+connect\b", re.IGNORECASE),
    re.compile(r"\bnetwork\s+is\s+unreachable\b", re.IGNORECASE),
    re.compile(r"\btemporary\s+failure\s+in\s+name\s+resolution\b", re.IGNORECASE),
    re.compile(r"\bfailed\s+to\s+refresh\s+available\s+models:\s*request\s+timed\s+out\b", re.IGNORECASE),
    re.compile(r"\bsocket\s+hang\s+up\b", re.IGNORECASE),
)


def detect_failover_reason(output: str, exit_code: Optional[int] = None) -> Optional[str]:
    """Detect if an agent output/error indicates quota exhaustion or connection refusal."""
    if not output or exit_code == 0:
        return None
    for pat in FAILOVER_PATTERNS_QUOTA:
        if pat.search(output):
            return "quota_limit"
    for pat in FAILOVER_PATTERNS_CONNECTION:
        if pat.search(output):
            return "connection_refused"
    return None


class OrchestrationError(ValueError):
    pass


def now():
    return datetime.now().astimezone().isoformat(timespec='seconds')


def validate_model(model):
    if model is not None and (not isinstance(model, str) or not model.strip()
                              or len(model) > 200 or model.startswith('-')
                              or any(char.isspace() or ord(char) < 32 for char in model)):
        raise OrchestrationError('model must be a nonempty model identifier of at most 200 characters')
    return model


def clear_task_brief(prompt):
    """Turn a voice/orchestrator payload into a concise English agent brief.

    Voice routing sometimes hands the supervisor a serialized envelope.  That
    envelope is useful internally, but exposing it to a worker makes the task
    look like a protocol dump.  Keep recognised context fields and render them
    as readable instructions; ordinary prompts pass through unchanged.
    """
    if not isinstance(prompt, str):
        return prompt
    text = prompt.strip()
    if not text.startswith('{'):
        return text
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return text
    if not isinstance(payload, dict):
        return text
    task = payload.get('task') or payload.get('prompt') or payload.get('goal')
    if not isinstance(task, str) or not task.strip():
        return text
    lines = ["Task", task.strip()]
    context = payload.get('context') or payload.get('background')
    if isinstance(context, str) and context.strip():
        lines.extend(["", "Context", context.strip()])
    deliverables = payload.get('deliverables') or payload.get('requirements')
    if isinstance(deliverables, list):
        items = [str(item).strip() for item in deliverables if str(item).strip()]
        if items:
            lines.extend(["", "Expected result", *[f"- {item}" for item in items]])
    constraints = payload.get('constraints')
    if isinstance(constraints, list):
        items = [str(item).strip() for item in constraints if str(item).strip()]
        if items:
            lines.extend(["", "Constraints", *[f"- {item}" for item in items]])
    return "\n".join(lines)


def command_for(agent, executable, prompt, model=None):
    validate_model(model)
    prompt = clear_task_brief(prompt)
    # A fixed prefix ensures prompts cannot be interpreted as command flags.
    message = prompt
    commands = {
        'codex': [executable, 'exec', '--sandbox', 'workspace-write', message],
        'claude': [executable, '--print', '--permission-mode', 'acceptEdits',
                   '--permission-prompts', 'none', message],
        'opencode': [executable, 'run', '--standalone', message],
        'gemini': [executable, '--prompt', message,
                   '--approval-mode', 'auto_edit', '--skip-trust'],
        'antigravity': [executable, '--mode', 'accept-edits', '--sandbox',
                        '--disable-slash-commands', '--print=' + message],
        'hermes': [executable, '-z', message],
        'omp': [executable, '--print', '--approval-mode', 'write', message],
        'pi': [executable, '--print', message],
        'crush': [executable, 'run', '--quiet', message],
        'api_agent': [executable, message],
    }
    command = commands[agent]
    if model:
        # Keep option values (such as Hermes -z and Gemini --prompt) intact.
        position = 2 if agent in ('codex', 'opencode', 'crush') else 1
        command[position:position] = ['--model', model]
    return command

class AgentOrchestrator:
    def __init__(self, executables=None, command_builder=command_for):
        self.executables = (dict(executables) if executables is not None else
                            installed_executables())
        self._command_builder = command_builder
        self.jobs = {}
        self.workers = {}
        self.processes = {}
        self.events = asyncio.Queue(maxsize=100)
        self.teams = {}
        self.team_workers = {}
        self._graphs = {}
        self._closed = False
        self._stopped = False
        self._stop_task = None
        self.harness2 = Harness2Adapter()
        self._agent_health = {}
        self._secrets = [value for name, value in os.environ.items()
                         if any(word in name.upper() for word in ('API_KEY', 'TOKEN', 'PASSWORD', 'SECRET'))
                         and len(value) >= 8]

    def is_agent_healthy(self, agent: str) -> bool:
        """Check if an agent is installed and not currently in failure cooldown."""
        if not self.executables.get(agent):
            return False
        health = self._agent_health.get(agent)
        if health and not health.get('healthy', True):
            if time.monotonic() < health.get('cooldown_until', 0):
                return False
            health['healthy'] = True
        return True

    def mark_agent_unhealthy(self, agent: str, reason: str, cooldown_seconds: float = 300.0):
        """Mark an agent unhealthy with a temporary cooldown."""
        now_mono = time.monotonic()
        self._agent_health[agent] = {
            'healthy': False,
            'reason': reason,
            'last_failure': now_mono,
            'cooldown_until': now_mono + cooldown_seconds,
        }

    def mark_agent_healthy(self, agent: str):
        """Manually restore an agent's healthy status."""
        self._agent_health.pop(agent, None)

    def select_fallback_agent(self, agent: str, attempted: set[str],
                              specified_fallbacks: Optional[list[str]] = None) -> Optional[str]:
        """Select next healthy available agent for failover."""
        candidates = list(specified_fallbacks) if specified_fallbacks else list(get_fallback_candidates(agent))
        for a in AGENTS:
            if a not in candidates:
                candidates.append(a)

        # 1. First pass: installed, unattempted, healthy
        for cand in candidates:
            if cand not in attempted and bool(self.executables.get(cand)) and self.is_agent_healthy(cand):
                return cand

        # 2. Second pass: installed, unattempted (even if in cooldown)
        for cand in candidates:
            if cand not in attempted and bool(self.executables.get(cand)):
                return cand

        return None

    def _response(self, summary, **data):
        return {'status': 'success', 'summary': summary, 'next_actions': [],
                'artifacts': [], **data}

    def _preflight_team(self, assignments):
        """Validate a normalized plan before it can create a team worker."""

    def _prepare_prompt(self, job, prompt):
        """Apply orchestration context before any agent frontend is launched.

        Desktop execution overrides ``_run`` and therefore cannot rely on the
        background implementation to add Harness² context.  Keep injected
        command builders byte-for-byte compatible with existing integrations.
        """
        if self._command_builder is command_for:
            prompt = clear_task_brief(prompt)
            role = job.get('role') or PERSONAS.get(job.get('agent'), {}).get('role')
            return self.harness2.prepare_prompt(
                prompt, agent=job['agent'], workspace=job['workspace'], role=role)
        return prompt

    def discover(self):
        return self._response('Installed agent commands discovered; authentication is not verified.',
            agents=[{'name': name, 'available': bool(self.executables.get(name)),
                     'executable': self.executables.get(name), **PERSONAS[name]} for name in AGENTS],
            harness2=self.harness2.status(), unsupported_agents=[])

    def delegate(self, agent, prompt, workspace, timeout_seconds=900, model=None, role=None, task_type=None,
                 fallback_agents=None, auto_failover=True, **extra):
        validate_model(model)
        if self._closed:
            raise OrchestrationError('orchestrator has stopped; restart JARVIS')
        if self._stopped:
            raise OrchestrationError('agent work is stopped; resume JARVIS before delegating')
        if agent not in AGENTS or not self.executables.get(agent):
            raise OrchestrationError('agent is unavailable; use list_system_agents')
        if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 20000:
            raise OrchestrationError('task prompt must be 1 to 20000 characters')
        if not isinstance(workspace, str) or not Path(workspace).expanduser().is_absolute():
            raise OrchestrationError('workspace must be an absolute directory path')
        try:
            root = Path(workspace).expanduser().resolve(strict=True)
        except (OSError, ValueError):
            raise OrchestrationError('workspace does not exist') from None
        if not root.is_dir() or root == Path('/'):
            raise OrchestrationError('workspace must be a specific existing directory')
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 10 <= timeout_seconds <= 7200:
            raise OrchestrationError('timeout must be from 10 to 7200 seconds')
        active = [job for job in self.jobs.values() if job['state'] not in TERMINAL]
        if len(active) >= 4:
            raise OrchestrationError('four agents are already active; wait or cancel a job')
        for job in active:
            other = Path(job['workspace'])
            if root == other or root in other.parents or other in root.parents:
                raise OrchestrationError(f'workspace is reserved by job {job["id"]}; wait or use a separate checkout')
        for team in self.teams.values():
            if team['state'] != 'cleanup_failed':
                continue
            other = Path(team['workspace'])
            if root == other or root in other.parents or other in root.parents:
                raise OrchestrationError(
                    f'workspace is reserved by team {team["id"]}; terminal cleanup is unconfirmed')
        if len(self.jobs) >= 50:
            oldest = next(key for key, job in self.jobs.items() if job['state'] in TERMINAL)
            del self.jobs[oldest]
        job_id = uuid.uuid4().hex[:12]
        job_role = role or task_type or PERSONAS.get(agent, {}).get('role')
        job = {'id': job_id, 'agent': agent, 'initial_agent': agent, 'model': model, 'role': job_role, 'workspace': str(root), 'state': 'queued',
               'task_summary': prompt.strip()[:200],
               'created_at': now(), 'updated_at': now(), 'exit_code': None,
               'output': '', 'output_truncated': False, 'cancel_requested': False,
               'auto_failover': auto_failover,
               'fallback_agents': list(fallback_agents) if fallback_agents else None,
               'failover_history': [],
               'auto_healed': False}
        self.jobs[job_id] = job
        self.workers[job_id] = asyncio.create_task(self._run(job_id, prompt, timeout_seconds))
        self.workers[job_id].add_done_callback(lambda done, key=job_id: self.workers.pop(key, None))
        return self.status(job_id)

    def _append(self, job, text):
        for secret in self._secrets:
            text = text.replace(secret, '[redacted]')
        combined = job['output'] + text
        if len(combined) > 64000:
            job['output_truncated'] = True
        job['output'] = combined[-64000:]
        job['updated_at'] = now()

    async def _read(self, job, stream):
        import codecs
        decoder = codecs.getincrementaldecoder('utf-8')(errors='replace')
        while chunk := await stream.read(4096):
            self._append(job, decoder.decode(chunk))
        self._append(job, decoder.decode(b'', final=True))

    async def _stop_process(self, process):
        if process is None:
            return
        # Signal the group even if its leader has exited but left helpers alive.
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            await asyncio.wait_for(process.wait(), 2)
        except TimeoutError:
            pass
        # The leader can exit while a helper ignores TERM and still holds pipes.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        await process.wait()

    async def _run(self, job_id, prompt, timeout_seconds):
        job = self.jobs[job_id]
        attempted_agents = set()
        original_prompt = prompt

        try:
            while True:
                current_agent = job['agent']
                attempted_agents.add(current_agent)
                process = None
                readers = []
                try:
                    if job['cancel_requested']:
                        job['state'] = 'cancelled'
                        return
                    # Preserve injected builders used by tests and integrations; the
                    # production command path receives the Harness² context.
                    current_prompt = self._prepare_prompt(job, original_prompt)
                    arguments = (current_agent, self.executables[current_agent], current_prompt)
                    # Existing injected builders use the original three-argument contract.
                    command = (command_for(*arguments, model=job.get('model'))
                               if self._command_builder is command_for else self._command_builder(*arguments))
                    process = await asyncio.create_subprocess_exec(
                        *command,
                        cwd=job['workspace'], stdin=asyncio.subprocess.DEVNULL,
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                        start_new_session=True, env=sanitized_subprocess_env(PATH=installed_path()))
                    self.processes[job_id] = process
                    job['state'] = 'running'
                    if job['cancel_requested']:
                        await self._stop_process(process)
                    readers = [asyncio.create_task(self._read(job, stream))
                               for stream in (process.stdout, process.stderr)]
                    try:
                        await asyncio.wait_for(process.wait(), timeout_seconds)
                        await asyncio.wait_for(asyncio.gather(*readers), 3)
                        if job['cancel_requested']:
                            job['state'] = 'cancelled'
                            break
                        if process.returncode == 0:
                            job['state'] = 'completed'
                            if len(attempted_agents) > 1:
                                job['auto_healed'] = True
                            break
                        else:
                            reason = detect_failover_reason(job['output'], process.returncode)
                            if reason and job.get('auto_failover', True) and not job['cancel_requested']:
                                fallback = self.select_fallback_agent(
                                    current_agent,
                                    attempted=attempted_agents,
                                    specified_fallbacks=job.get('fallback_agents'),
                                )
                                if fallback:
                                    self.mark_agent_unhealthy(current_agent, reason=reason)
                                    job['failover_history'].append({
                                        'agent': current_agent,
                                        'exit_code': process.returncode,
                                        'reason': reason,
                                        'timestamp': now(),
                                    })
                                    msg = (
                                        f"\n[Auto-Healing] Agent '{current_agent}' failed ({reason}). "
                                        f"Attempting failover to healthy agent '{fallback}'...\n"
                                    )
                                    self._append(job, msg)
                                    job['agent'] = fallback
                                    job['role'] = PERSONAS.get(fallback, {}).get('role', job.get('role'))
                                    await self._stop_process(process)
                                    self.processes.pop(job_id, None)
                                    continue
                            job['state'] = 'cancelled' if job['cancel_requested'] else 'failed'
                            break
                    except TimeoutError:
                        job['state'] = 'timed_out'
                        break
                    if job['cancel_requested']:
                        job['state'] = 'cancelled'
                        break
                except asyncio.CancelledError:
                    job['state'] = 'cancelled'
                    break
                except Exception as error:
                    if job['cancel_requested']:
                        job['state'] = 'cancelled'
                        break
                    reason = detect_failover_reason(str(error)) or f"Launch error: {type(error).__name__}"
                    if job.get('auto_failover', True):
                        fallback = self.select_fallback_agent(
                            current_agent,
                            attempted=attempted_agents,
                            specified_fallbacks=job.get('fallback_agents'),
                        )
                        if fallback:
                            self.mark_agent_unhealthy(current_agent, reason=reason)
                            job['failover_history'].append({
                                'agent': current_agent,
                                'exit_code': None,
                                'reason': reason,
                                'timestamp': now(),
                            })
                            msg = (
                                f"\n[Auto-Healing] Agent '{current_agent}' launch failure ({reason}). "
                                f"Attempting failover to healthy agent '{fallback}'...\n"
                            )
                            self._append(job, msg)
                            job['agent'] = fallback
                            job['role'] = PERSONAS.get(fallback, {}).get('role', job.get('role'))
                            continue
                    job['state'] = 'failed'
                    self._append(job, f'\nLaunch failed: {type(error).__name__}: {error}\n')
                    break
                finally:
                    await self._stop_process(process)
                    for reader in readers:
                        if not reader.done():
                            reader.cancel()
                    if readers:
                        await asyncio.gather(*readers, return_exceptions=True)
                    if process is not None:
                        job['exit_code'] = process.returncode
                    self.processes.pop(job_id, None)
        finally:
            if job.get('cancel_requested'):
                job['state'] = 'cancelled'
            job['updated_at'] = now()
            if self.events.full():
                self.events.get_nowait()
            self.events.put_nowait({key: job[key] for key in ('id', 'agent', 'state', 'workspace')})
            self.harness2.record_outcome(agent=job['agent'], task=job['task_summary'],
                                         state=job['state'], output=job['output'])

    def status(self, job_id, max_chars=6000):
        job = self.jobs.get(job_id)
        if job is None:
            raise OrchestrationError('agent job not found; use list_agent_jobs')
        if not isinstance(max_chars, int) or not 100 <= max_chars <= 20000:
            raise OrchestrationError('output limit must be from 100 to 20000 characters')
        result = {**job, 'output': job['output'][-max_chars:],
                  'output_truncated': job['output_truncated'] or len(job['output']) > max_chars}
        return self._response(f'{job["agent"]} job is {job["state"]}.', job=result,
            next_actions=(['check_agent_job', 'cancel_agent_job'] if job['state'] not in TERMINAL else []),
            artifacts=[job_id, job['workspace']])

    def list_jobs(self):
        return self._response('Agent job summaries.', jobs=[
            {key: value for key, value in job.items() if key != 'output'}
            for job in self.jobs.values()])

    def delegate_team(self, goal, assignments, workspace, timeout_seconds=900, max_retries_per_stage=0):
        """Run a bounded, model-planned team sequentially in one workspace with StateGraph tracking."""
        if self._closed:
            raise OrchestrationError('orchestrator has stopped; restart JARVIS')
        if self._stopped:
            raise OrchestrationError('agent work is stopped; resume JARVIS before delegating')
        if not isinstance(goal, str) or not 1 <= len(goal.strip()) <= 4000:
            raise OrchestrationError('team goal must be 1 to 4000 characters')
        if not isinstance(assignments, list) or not 1 <= len(assignments) <= 6:
            raise OrchestrationError('team assignments must contain 1 to 6 tasks')
        if isinstance(max_retries_per_stage, bool) or not isinstance(max_retries_per_stage, int) or not 0 <= max_retries_per_stage <= 5:
            raise OrchestrationError('max_retries_per_stage must be an integer from 0 to 5')
        if not isinstance(workspace, str) or not Path(workspace).expanduser().is_absolute():
            raise OrchestrationError('workspace must be an absolute directory path')
        try:
            root = Path(workspace).expanduser().resolve(strict=True)
        except (OSError, ValueError):
            raise OrchestrationError('workspace does not exist') from None
        if not root.is_dir() or root == Path('/'):
            raise OrchestrationError('workspace must be a specific existing directory')
        for team in self.teams.values():
            if team['state'] != 'cleanup_failed':
                continue
            other = Path(team['workspace'])
            if root == other or root in other.parents or other in root.parents:
                raise OrchestrationError(
                    f'workspace is reserved by team {team["id"]}; terminal cleanup is unconfirmed')
        if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, int) or not 10 <= timeout_seconds <= 7200:
            raise OrchestrationError('timeout must be from 10 to 7200 seconds')
        normalized = []
        for index, item in enumerate(assignments):
            if not isinstance(item, dict):
                raise OrchestrationError(f'assignment {index + 1} must be an object')
            agent = item.get('agent')
            prompt = item.get('prompt')
            validate_model(item.get('model'))
            if agent not in AGENTS or not self.executables.get(agent):
                raise OrchestrationError(f'assignment {index + 1} agent is unavailable')
            if not isinstance(prompt, str) or not 1 <= len(prompt.strip()) <= 20000:
                raise OrchestrationError(f'assignment {index + 1} prompt must be 1 to 20000 characters')
            normalized.append({
                'agent': agent,
                'prompt': prompt.strip(),
                'task_type': item.get('task_type', 'coding'),
                'model': item.get('model'),
                'visible': item.get('visible', True),
                'batch': item.get('batch', False),
                'yolo': item.get('yolo', False),
            })
        self._preflight_team(normalized)
        team_id = 'team-' + uuid.uuid4().hex[:10]
        state_graph = TeamStateGraph(
            team_id=team_id,
            goal=goal.strip(),
            workspace=str(root),
            total_assignments=len(normalized),
            max_retries_per_stage=max_retries_per_stage,
        )
        self._graphs[team_id] = state_graph
        team = {
            'id': team_id, 'goal': goal.strip(), 'workspace': str(root),
            'state': 'queued', 'assignments': normalized, 'current_assignment': None,
            'jobs': [], 'cancel_requested': False, 'created_at': now(), 'updated_at': now(),
            'max_retries_per_stage': max_retries_per_stage,
            'state_graph': state_graph.to_dict(),
        }
        self.teams[team_id] = team
        worker = asyncio.create_task(self._run_team(team_id, timeout_seconds))
        self.team_workers[team_id] = worker
        worker.add_done_callback(lambda done, key=team_id: self.team_workers.pop(key, None))
        return self.team_status(team_id)

    async def _run_team(self, team_id, timeout_seconds):
        team = self.teams[team_id]
        team['state'] = 'running'
        state_graph = self._graphs.get(team_id)
        if state_graph is None:
            state_graph = TeamStateGraph(
                team_id=team_id,
                goal=team['goal'],
                workspace=team['workspace'],
                total_assignments=len(team['assignments']),
                max_retries_per_stage=team.get('max_retries_per_stage', 0),
            )
            self._graphs[team_id] = state_graph
        state_graph.state = 'running'
        team['state_graph'] = state_graph.to_dict()

        try:
            index = 0
            while index < len(team['assignments']):
                if team['cancel_requested'] or self._closed or self._stopped:
                    team['state'] = 'cancelled'
                    state_graph.state = 'cancelled'
                    team['state_graph'] = state_graph.to_dict()
                    return

                assignment = team['assignments'][index]
                team['current_assignment'] = index
                state_graph.current_index = index

                retry_count = state_graph.retry_counts.get(index, 0)
                is_retry = retry_count > 0
                last_err = ""
                if is_retry and team['jobs']:
                    last_job_id = team['jobs'][-1]
                    if last_job_id in self.jobs:
                        last_err = self.jobs[last_job_id]['output']

                context = state_graph.build_node_context(
                    assignment=assignment,
                    index=index,
                    is_retry=is_retry,
                    last_failure_output=last_err
                )

                result = self._delegate_team_assignment(
                    assignment, context, team['workspace'], timeout_seconds)
                job_id = result['job']['id']
                team['jobs'].append(job_id)
                team['updated_at'] = now()
                await self.workers[job_id]

                job_res = self.jobs[job_id]
                state_graph.record_step(
                    job_id=job_id,
                    agent=assignment['agent'],
                    index=index,
                    prompt=assignment['prompt'],
                    state=job_res['state'],
                    output=job_res.get('output', ''),
                    error=job_res.get('error')
                )
                team['state_graph'] = state_graph.to_dict()

                edge_action = state_graph.evaluate_edge(index, job_res['state'])
                if edge_action == EdgeAction.COMPLETE:
                    team['state'] = 'completed'
                    state_graph.state = 'completed'
                    team['state_graph'] = state_graph.to_dict()
                    team['verification'] = 'Agent stages finished; inspect QA and review evidence before claiming success.'
                    return
                elif edge_action == EdgeAction.PROCEED:
                    index += 1
                elif edge_action == EdgeAction.RETRY:
                    # Self-healing cyclic retry loop: repeat this stage with diagnostic context
                    continue
                else:  # EdgeAction.FAIL
                    team['state'] = 'failed'
                    state_graph.state = 'failed'
                    team['state_graph'] = state_graph.to_dict()
                    return

            team['state'] = 'completed'
            state_graph.state = 'completed'
            team['state_graph'] = state_graph.to_dict()
            team['verification'] = 'Agent stages finished; inspect QA and review evidence before claiming success.'
        except asyncio.CancelledError:
            team['state'] = 'cancelled'
            state_graph.state = 'cancelled'
            team['state_graph'] = state_graph.to_dict()
            raise
        except Exception as error:
            team['state'] = 'failed'
            state_graph.state = 'failed'
            team['error'] = str(error)[:500]
            team['state_graph'] = state_graph.to_dict()
        finally:
            team['current_assignment'] = None
            team['updated_at'] = now()
            if self.events.full():
                self.events.get_nowait()
            self.events.put_nowait({'kind': 'team', 'id': team_id, 'state': team['state'],
                                   'workspace': team['workspace']})

    def _delegate_team_assignment(self, assignment, prompt, workspace, timeout_seconds):
        return self.delegate(assignment['agent'], prompt, workspace, timeout_seconds,
                             model=assignment.get('model'))

    def team_status(self, team_id):
        team = self.teams.get(team_id)
        if team is None:
            raise OrchestrationError('agent team not found')
        return self._response(f'Agent team is {team["state"]}.', team={**team},
                              artifacts=[team_id, team['workspace']])

    async def cancel_team(self, team_id):
        if team_id not in self.teams:
            raise OrchestrationError('agent team not found')
        team = self.teams[team_id]
        worker = self.team_workers.get(team_id)
        if team['state'] in TERMINAL and (worker is None or worker.done()):
            return self.team_status(team_id)
        team['cancel_requested'] = True
        for job_id in team['jobs']:
            if self.jobs[job_id]['state'] not in TERMINAL:
                await self.cancel(job_id)
        if worker and not worker.done():
            if team['state'] not in TERMINAL:
                worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
        team['state'] = 'cancelled'
        team['updated_at'] = now()
        return self.team_status(team_id)

    def stop_admission(self):
        """Latch stop intent before yielding to persistence or cancellation."""
        self._stopped = True
        for team in self.teams.values():
            if team['state'] not in TERMINAL:
                team['cancel_requested'] = True
        for job in self.jobs.values():
            if job['state'] not in TERMINAL:
                job['cancel_requested'] = True

    def resume(self):
        if self._stop_task is not None and not self._stop_task.done():
            raise OrchestrationError('agent work is still stopping; wait before resuming')
        self._stopped = False

    async def stop_all(self):
        self.stop_admission()
        if self._stop_task is None or self._stop_task.done():
            self._stop_task = asyncio.create_task(self._cancel_all())
            self._stop_task.add_done_callback(
                lambda done: None if done.cancelled() else done.exception())
        # A cancelled voice tool must not abandon the stop operation.
        await asyncio.shield(self._stop_task)

    async def _cancel_all(self):
        for team_id in list(self.team_workers):
            await self.cancel_team(team_id)
        await asyncio.gather(*(self.cancel(key) for key in list(self.workers)))

    async def cancel(self, job_id):
        if job_id not in self.jobs:
            raise OrchestrationError('agent job not found; use list_agent_jobs')
        job = self.jobs[job_id]
        if job['state'] not in TERMINAL:
            job['cancel_requested'] = True
            # Wait for spawn to resolve rather than cancelling during process creation.
            await self._stop_process(self.processes.get(job_id))
            worker = self.workers.get(job_id)
            if worker:
                await worker
        return self.status(job_id)

    async def close(self):
        self._closed = True
        await self.stop_all()
