# CareerPulse A02 Development Rules

## Project goal

Upgrade CareerPulse into an AI career navigation and lifelong
learning companion based on Ant TBox Enterprise.

## Architecture

- Preserve stable existing CareerPulse functions.
- Ant TBox is a mandatory runtime and publishing platform.
- CareerOrchestrator controls the internal workflow.
- Agent handles reasoning and workflow decisions.
- Service handles deterministic calculations.
- Tool exposes reusable business capability.
- API/MCP exposes tools to Ant TBox and frontend.
- LLM output must be validated using Pydantic or JSON Schema.
- Match scores, gap analysis and path scores must not be invented by LLM.
- Every Agent and platform tool call must have a log.
- External model and tool failures require fallback.
- Demo Mode must work without external model APIs.
- Do not claim a platform capability unless it is actually configured and tested.

## Collaboration

- Public schemas are owned by the technical lead.
- Do not change public fields without updating API_CONTRACTS.md.
- Do not modify another member's files without approval.
- Do not rename database fields without migration.
- Platform tool schemas and backend schemas must remain consistent.

## Privacy

- Never commit real resume private information.
- Never log full resume text in platform or Agent logs.
- Mask phone numbers, emails, names and identity information.
- Never expose tokens or API keys in screenshots.

## Quality

- Every new Service requires tests.
- Every platform tool requires success and failure tests.
- Run tests after every task.
- Report modified files, tests and known risks.
- Do not automatically commit Git changes.