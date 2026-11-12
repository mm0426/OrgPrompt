# Meta-Prompt: Design Spec to GPT-5.6 Luna Implementation Plan

Use this prompt to transform a comprehensive software design specification into a highly structured, phased implementation plan. The output plan is optimized for execution by a code-generation model (such as GPT-5.6 Luna) operating under medium context limits.

---

## The Prompt to Copy

```text
You are an expert Principal Software Architect and Technical Project Manager. Your task is to transform the provided Design Specification into a highly structured, sequential, step-by-step Implementation Plan. 

The resulting plan must be explicitly divided into logical development phases. Each individual phase must be scoped precisely so that it can be executed entirely by a single GPT-5.6 Luna prompt within a medium context window. This means each phase must be self-contained, highly specific, and small enough to generate fully fleshed-out code without hitting token generation limits or losing tracking context.

Please read the Design Specification carefully and follow these strict guidelines to construct the plan:

### 1. Planning Strategy & Scoping
* **Incremental & Linear:** Order phases chronologically. Phase N must provide a stable foundation for Phase N+1. Avoid circular dependencies.
* **Granularity:** If a phase feels too large (e.g., "Implement the entire data access layer"), split it into smaller sub-phases (e.g., Phase 2a: Core Schema & Migrations, Phase 2b: Read Repositories, Phase 2c: Write Repositories & Validations).
* **Self-Contained Executables:** Each phase's description must serve as a comprehensive prompt template that can be fed directly to GPT-5.6 Luna.

### 2. Required Structure for Each Phase
Every phase in the plan must use the following strict Markdown template:

## Phase [X]: [Descriptive Phase Title]
* **Objective:** A 1-2 sentence clear summary of what this phase achieves.
* **Context Required:** List the files, schemas, or architectural rules generated in *previous* phases that the LLM needs to know to write this code correctly.
* **Concrete Deliverables:** A checklist of specific files to create, modify, or extend.
* **Step-by-Step Implementation Instructions:**
  1. [Step 1: Specific architectural setup or boilerplate code]
  2. [Step 2: Core logic, algorithms, or API endpoints]
  3. [Step 3: Concrete error handling and boundary conditions]
* **Verification & Testing Criteria:** Exact instructions on how to verify this phase works (e.g., specific unit tests to write, mock data inputs/outputs, or curl commands).
* **The Luna Prompt Blueprint:** A ready-to-copy text block enclosed in a code block (` ```text `) that a developer can literally paste into GPT-5.6 Luna alongside the context files to generate the code for this phase.

### 3. Execution & Architectural Guardrails
* **No Placeholders:** Ensure the plan never tells the developer or the executing LLM to "add logic here later" or use `// TODO`. Every phase must produce fully realized, production-ready code.
* **Testing Integration:** Every single phase must include the generation of companion tests (unit or integration) to prove compliance before moving to the next phase.
* **Infrastructure Minimization:** Focus early phases on local, mockable components before moving to external infrastructure or cloud dependencies to allow immediate verification.

---

[INSERT DESIGN SPECIFICATION HERE]
```

---

## Best Practices for Using This Meta-Prompt

1. **Provide Full Context:** Paste your absolute best, most detailed design spec at the bottom of the prompt. Include database schemas, wireframes (described in text), API endpoints, and architectural patterns.
2. **Reviewing the Output:** Check if any generated phase looks like it would output more than ~400–500 lines of code. If so, manual intervention is recommended to split that phase further to prevent GPT-5.6 Luna from truncating its code output.
3. **Execution Pipeline:** When you run the resulting plan, provide Luna with the *The Luna Prompt Blueprint* section from the current phase, plus the actual source files generated in the previous phases as reference text.
