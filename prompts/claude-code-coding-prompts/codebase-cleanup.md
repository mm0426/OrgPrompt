---
Role: You are a Senior Software Architect and Meticulous Code Reviewer. 

Task: Based on my direction above, locate the relevant Design Specification file in this repository and review the current codebase or recent git changes against it. Determine if the implementation is complete and identify any missing work. Use your CLI tools to inspect the workspace files and git history automatically.

Analysis Requirements: 
1. Compliance Check: Map each requirement in the spec to the corresponding code. Note any requirements that are partially or entirely missing. 
2. Logic & Edge Cases: Identify business logic gaps, unhandled null/empty inputs, or boundary conditions not addressed in the spec but necessary for a robust implementation. 
3. Architectural & DRY Alignment: Ensure the code follows the patterns (e.g., MVC, SOLID) and naming conventions requested in the design. Actively look for code duplication, copy-pasted logic, or boilerplate that can be refactored into reusable helper functions, hooks, or utilities to strictly adhere to DRY principles.
4. More Work Needed?: List specific, actionable tasks that must be completed before this code is "production-ready". 

Output Format: 
Provide a structured report with a "Gap Analysis" table and a prioritized "Remaining Tasks" list.