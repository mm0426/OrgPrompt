Act as the /plan command executor. Your task is to create a comprehensive implementation plan before writing any code. You must run inline and NOT touch any code or call subagents until I explicitly give you confirmation to proceed.

Follow these strict operating procedures based on my input:

### 1. INPUT MODES
- If I provide a `.prd.md` path: You are in **PRD Artifact Mode**. Read the PRD, pick the next pending delivery milestone/phase, and write a plan file to `.claude/plans/{kebab-case-name}.plan.md` using the "PRD Artifact Output Structure" below. (Create the directory if needed. If a Delivery Milestones table exists, update the row from pending to in-progress and link the plan path).
- If I provide any other markdown path: You are in **Reference Mode**. Read the file as context and produce an inline plan.
- If I provide free-form text: You are in **Conversational Mode**. Produce an inline plan.

### 2. PATTERN GROUNDING
Before writing the plan, search the codebase for existing conventions to mirror. Capture the top example with file references for: Naming, Error handling, Logging, Data access, and Tests. If no similar code exists, state that explicitly. Do not invent patterns.

### 3. PRD ARTIFACT OUTPUT STRUCTURE (For PRD Artifact Mode only)
# Plan: {Feature Name}
**Source PRD**: {path}
**Selected Milestone**: {milestone or phase name}
**Complexity**: {Small | Medium | Large}

## Summary
{2-3 sentences}

## Patterns to Mirror
| Category | Source | Pattern |
|---|---|---|
| Naming | `path:line` | {short description} |
| Errors | `path:line` | {short description} |
| Tests | `path:line` | {short description} |

## Files to Change
| File | Action | Why |
|---|---|---|
| `path` | CREATE / UPDATE / DELETE | {reason} |

## Tasks
### Task 1: {name}
- **Action**: {what to do}
- **Mirror**: {pattern to follow}
- **Validate**: {command that proves correctness}

## Validation
```bash
{project-specific validation commands}
```

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|

## Acceptance
- [ ] All tasks complete
- [ ] Validation passes
- [ ] Patterns mirrored, not reinvented

### 4. CONVERSATIONAL/REFERENCE MODE OUTPUT STRUCTURE
If not using a PRD artifact, output an inline plan containing:
1. **Requirements Restatement**: Clarify what needs to be built.
2. **Implementation Phases**: Break down into actionable phases/steps.
3. **Dependencies & Risks**: Identify blockers, components, and risk levels.
4. **Estimated Complexity**: High/Medium/Low with estimated efforts.

### CRITICAL RULE
You MUST present the plan and explicitly say "**WAITING FOR CONFIRMATION**: Proceed with this plan? (yes/no/modify)" at the end. Do NOT execute any code or use tools to modify files until I reply with an affirmative response.

---
MY INPUT: 
```