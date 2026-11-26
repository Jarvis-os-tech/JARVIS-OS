"""User-defined system-agent responsibilities and autonomous workflow."""

PERSONAS = {
    'hermes': {'role': 'Researcher and planner', 'core': True, 'fallbacks': ('gemini', 'opencode', 'claude')},
    'codex': {'role': 'Development engineer', 'core': True, 'fallbacks': ('claude', 'opencode', 'gemini', 'hermes')},
    'claude': {'role': 'Developer, reviewer and final tester', 'core': True, 'fallbacks': ('opencode', 'gemini', 'hermes', 'codex')},
    'antigravity': {'role': 'Development engineer', 'core': True, 'fallbacks': ('claude', 'opencode', 'gemini')},
    'opencode': {'role': 'Independent test engineer', 'core': True, 'fallbacks': ('claude', 'gemini', 'hermes')},
    'gemini': {'role': 'Optional research specialist', 'core': False, 'fallbacks': ('opencode', 'hermes', 'claude')},
    'omp': {'role': 'Optional coordination specialist', 'core': False, 'fallbacks': ('hermes', 'opencode', 'claude')},
    'pi': {'role': 'Optional development assistant', 'core': False, 'fallbacks': ('opencode', 'claude')},
    'crush': {'role': 'Optional development assistant', 'core': False, 'fallbacks': ('opencode', 'claude')},
    'api_agent': {'role': 'Web API reverse-engineering and execution specialist', 'core': False, 'fallbacks': ('gemini', 'hermes', 'opencode')},
}

AGENT_FALLBACK_CANDIDATES = {
    'codex': ('claude', 'opencode', 'gemini', 'hermes', 'omp'),
    'claude': ('opencode', 'gemini', 'hermes', 'codex', 'omp'),
    'opencode': ('claude', 'gemini', 'hermes', 'codex', 'omp'),
    'gemini': ('opencode', 'hermes', 'claude', 'omp'),
    'hermes': ('gemini', 'opencode', 'claude', 'omp'),
    'omp': ('hermes', 'opencode', 'claude'),
    'pi': ('opencode', 'claude', 'gemini'),
    'crush': ('opencode', 'claude', 'gemini'),
    'api_agent': ('gemini', 'hermes', 'opencode'),
}


def get_fallback_candidates(agent: str) -> tuple[str, ...]:
    """Retrieve ordered fallback agent candidates for a given agent."""
    if agent in AGENT_FALLBACK_CANDIDATES:
        return AGENT_FALLBACK_CANDIDATES[agent]
    return ('opencode', 'gemini', 'hermes', 'codex', 'claude', 'omp', 'pi', 'crush')


def software_assignments(executables, healthy_agents=None):
    """Require the core gates; select an installed development executor with autonomous fallback."""
    # Codex is temporarily excluded from primary developer selection at the user's request.
    is_healthy = lambda name: bool(executables.get(name)) and (healthy_agents is None or name in healthy_agents)

    developer = None
    if is_healthy('claude'):
        developer = 'claude'
    else:
        for candidate in ('opencode', 'gemini', 'hermes', 'codex'):
            if is_healthy(candidate):
                developer = candidate
                break
        if developer is None and executables.get('claude'):
            developer = 'claude'

    missing = [name for name in ('hermes', 'opencode', 'claude') if not executables.get(name)]
    if missing or developer is None:
        raise ValueError('Autonomous workflow requires installed agents: ' + ', '.join(missing or ['claude']))

    reviewer = 'claude' if is_healthy('claude') else ('opencode' if is_healthy('opencode') else developer)
    planner = 'hermes' if is_healthy('hermes') else ('gemini' if is_healthy('gemini') else 'opencode')
    qa = 'opencode' if is_healthy('opencode') else developer

    return [
        {'agent': planner, 'visible': True, 'batch': False, 'yolo': True, 'prompt':
         'Research the goal and inspect project evidence. Distinguish proven facts from inferences. '
         'Produce a concrete implementation plan, acceptance criteria and test strategy following non-destructive Omarchy invariants. '
         'Do not change application source.'},
        {'agent': developer, 'visible': True, 'batch': False, 'yolo': True, 'prompt':
         'Implement the goal using the preceding research and plan. Follow Omarchy standards: preserve unrelated edits, '
         'adhere to zero-polling architecture and purposeful motion budgets, never touch /usr/share/omarchy (use ~/.config overrides with backups), '
         'and do not modify or override locked voice core files (audio/engine.py, audio/downstream.py, audio/echo_cancel.py). '
         'Run relevant checks and report changed files and limitations.'},
        {'agent': qa, 'visible': True, 'batch': False, 'yolo': True, 'prompt':
         'Independently test the implementation against the goal and acceptance criteria. Work strictly from evidence: '
         'run relevant tests, investigate failures and add regression tests where needed. '
         'Report exact evidence and remaining defects; do not claim success without checks.'},
        {'agent': reviewer, 'visible': True, 'batch': False, 'yolo': True, 'prompt':
         'Review implementation and independent QA evidence. Fix remaining defects within scope, '
         'rerun affected tests and perform final verification. Preserve locked voice core files. '
         'Report unresolved issues explicitly. '
         'Do not publish, deploy or merge changes unless the original user request authorizes it.'},
    ]
