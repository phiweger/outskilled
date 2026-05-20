---
name: extract-method
description: How to safely extract a sub-block of a long function into its own named method.
when_to_use: When the user asks to refactor a long function, pull out a helper, or shorten a method that does too much.
allowed-tools:
  - "Read"
  - "Edit"
---

# Extract method

1. Identify the sub-block. Look for a contiguous run of statements
   that share a clear purpose and use a bounded set of variables.
2. Name it. The name should describe **what** the block does, not how.
   Verb-first, ≤4 words.
3. Determine inputs and outputs:
   - Inputs are variables read in the block but defined before it.
   - Outputs are variables written in the block and used after it.
4. If there is exactly one output, the new method returns it.
   If there are multiple, return a tuple or a small dataclass — do
   not mutate caller-scope state via globals.
5. Move the block into a new function with the inputs as parameters.
6. Replace the original block with a call to the new function.
7. Run the test suite. If there is none, write at least one
   characterisation test before extracting.
