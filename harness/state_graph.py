"""Typed StateGraph and Supervisor Edge Routing for JARVIS Multi-Agent Orchestration.

Implements the 4 foundational Multi-Agent concepts:
1. StateGraph: Typed, shared working memory checkpointed across all specialist stages.
2. Nodes: Specialized agents/tools receiving state and returning bounded updates.
3. Edges: Dynamic fixed and conditional connections determined at runtime.
4. Loops vs Chains: Cyclic retry, critique feedback, and self-healing instead of rigid DAGs.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class EdgeAction(str, Enum):
    PROCEED = "proceed"       # Step succeeded -> move to next node (A -> B)
    RETRY = "retry"           # Step failed but budget remains -> loop back with diagnostic feedback
    FAIL = "fail"             # Step failed and retry budget exhausted -> terminate
    COMPLETE = "complete"     # Final node succeeded -> graph terminal state


@dataclass
class NodeExecutionRecord:
    job_id: str
    agent: str
    assignment_index: int
    prompt: str
    state: str
    output_snippet: str
    error: Optional[str] = None
    retry_attempt: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec='seconds'))


@dataclass
class TeamStateGraph:
    """System working memory (StateGraph) for multi-agent collaboration."""
    team_id: str
    goal: str
    workspace: str
    total_assignments: int
    current_index: int = 0
    max_retries_per_stage: int = 1
    state: str = "queued"
    retry_counts: Dict[int, int] = field(default_factory=dict)
    artifacts: Dict[str, str] = field(default_factory=dict)
    history: List[NodeExecutionRecord] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec='seconds'))
    updated_at: str = field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec='seconds'))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "team_id": self.team_id,
            "goal": self.goal,
            "workspace": self.workspace,
            "total_assignments": self.total_assignments,
            "current_index": self.current_index,
            "max_retries_per_stage": self.max_retries_per_stage,
            "state": self.state,
            "retry_counts": self.retry_counts,
            "artifacts": self.artifacts,
            "history": [asdict(h) for h in self.history],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def record_step(self, job_id: str, agent: str, index: int, prompt: str, state: str,
                    output: str, error: Optional[str] = None) -> NodeExecutionRecord:
        snippet = output[-3000:] if output else ""
        retry_num = self.retry_counts.get(index, 0)
        rec = NodeExecutionRecord(
            job_id=job_id,
            agent=agent,
            assignment_index=index,
            prompt=prompt,
            state=state,
            output_snippet=snippet,
            error=error,
            retry_attempt=retry_num,
        )
        self.history.append(rec)
        self.updated_at = datetime.now().astimezone().isoformat(timespec='seconds')
        
        # If output contains structured artifact tags or summary, store in working memory
        if state == "completed" and snippet:
            self.artifacts[f"stage_{index}_{agent}"] = snippet
        return rec

    def evaluate_edge(self, index: int, job_state: str) -> EdgeAction:
        """Evaluate conditional edges: decide whether to proceed, loop/retry, or fail."""
        if job_state == "completed":
            if index + 1 >= self.total_assignments:
                return EdgeAction.COMPLETE
            return EdgeAction.PROCEED

        # The step did not complete successfully
        current_retries = self.retry_counts.get(index, 0)
        if current_retries < self.max_retries_per_stage:
            self.retry_counts[index] = current_retries + 1
            return EdgeAction.RETRY
        return EdgeAction.FAIL

    def build_node_context(self, assignment: Dict[str, Any], index: int,
                           is_retry: bool = False, last_failure_output: str = "") -> str:
        """Construct structured working-memory prompt with artifact context and retry loops."""
        lines = [
            f"=== MULTI-AGENT STATE GRAPH CONTEXT ===",
            f"Team Goal: {self.goal}",
            f"Active Node: {assignment['agent']} (Stage {index + 1}/{self.total_assignments})",
        ]

        if is_retry:
            retry_num = self.retry_counts.get(index, 0)
            lines.extend([
                f"\n>>> [CRITIQUE / SELF-HEAL LOOP: ATTEMPT {retry_num + 1}] <<<",
                "The previous execution of this stage did not reach verified completion.",
                "Review the diagnostic error output below, correct the failure, and ensure all checks pass.",
                f"Prior Failure Output Diagnostic:\n{last_failure_output[-2000:] if last_failure_output else 'No output captured.'}",
                ">>> END DIAGNOSTIC <<<\n",
            ])

        lines.extend([
            f"\nAssigned Stage Prompt:",
            f"{assignment['prompt']}",
            "\nGuidelines:",
            "- Inspect the workspace working memory and previous specialist artifacts.",
            "- Confine modifications to this specialized stage.",
            "- Validate changes and leave the workspace cleanly prepared for subsequent nodes.",
        ])

        # Inject checkpointed artifacts from earlier nodes
        if self.artifacts:
            lines.append("\n=== CHECKPOINTED WORKING MEMORY ARTIFACTS ===")
            for key, val in self.artifacts.items():
                lines.append(f"[{key}]:\n{val[-1500:]}\n")

        return "\n".join(lines)
