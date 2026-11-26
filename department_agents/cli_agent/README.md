# CLI-Agent department

Four bounded agents own existing CLI-Anything, API-Anything, Composio and
Agent-Reach tools. They are routing metadata, not independent model processes.

`DesktopSkills.execute` validates owned calls before routing them through
`CLIAgentDepartment` to the existing adapter and verification path. Antigravity
uses the native `agy` executable. A submitted job is only a connection attempt.
Check its result before reporting a connection.
`request_capability` queues a CLI Agent development job. After baseline checks,
it sends a `plan` request to `jarvis-cli-agent.service` on its private user socket.
The configured low-cost NVIDIA NIM model drafts a connection plan. A local
researcher validates the plan before the existing implementation, test, and
review stages. The request goes to NIM, so omit credentials and private data.
Development currently ends with a proposal for review.

Keep permission checks, input validation, subprocess handling and credentials
in the existing adapters and connectors. The department adds no shell runner,
installs, network calls or credentials. It forwards results and errors unchanged:
installed/configured is not verified readiness, and process success is not
proof of an external effect. API write authorization and native Google/GitHub
routing boundaries remain the responsibility of the existing dispatcher.
