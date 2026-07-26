# End-to-End Test Plan

This plan verifies the real GitHub Action without using production repositories or company code.

## Prerequisites

- A private GitHub repository for the Action and a separate private Java/Spring demo repository.
- A DeepSeek API key stored as the DEEPSEEK_API_KEY Actions secret in the demo repository.
- The Action published to a branch or a version tag accessible to the demo repository.

## Demo repository setup

1. Add the two invariant Markdown files under .guardian/invariants.
2. Add a workflow that invokes the Action from its repository branch with contents read and pull-requests write permissions.
3. Pass DEEPSEEK_API_KEY only through the Action's llm-api-key input. Do not expose it to shell steps.

## Required scenarios

| Scenario | Expected result |
| --- | --- |
| PR adds @Scheduled and changes the watched order state | One evidence-cited invariant assessment comment with a confirmed monitoring violation. |
| PR returns OrderEntity from a public controller | One evidence-cited domain-leak violation. |
| PR returns OrderResponse DTO | No confirmed violation comment. |
| Re-run unchanged PR workflow | Existing comment is unchanged; no duplicate comment. |
| Remove the violation and push a correction | Existing comment updates to no confirmed violations. |
| Open a fork PR | No provider key is used and no comment is published. |
| Invalid provider key or provider outage | Action reports assessment incomplete, never a clean result. |

## Cost guardrail

Run one live model request per deliberate violation scenario. Keep the diff fixtures small, set max_output_tokens to the current code limit, and record provider usage from the response before expanding the fixture set.

## Evidence to retain

- Workflow run URLs or screenshots.
- Before/after pull-request comments.
- The exact invariant files and fixture diff for each scenario.
- Provider usage, latency, and whether the judgment was confirmed, rejected, or incomplete.
