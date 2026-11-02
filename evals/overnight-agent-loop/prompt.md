---
description: Designs a bounded, safe autonomous coding loop
tags: [agents, core]
runs: 3
max_turns: 15
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
plugins: ["../.."]
---

I want to run a coding agent overnight in a loop that keeps fixing failing tests in our monorepo until everything is green, then opens a pull request. How should I set this up safely?
