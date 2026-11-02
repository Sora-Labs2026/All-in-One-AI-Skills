---
description: Does not load the skill for a question outside its scope
tags: [negative, core]
runs: 3
max_turns: 3
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
plugins: ["../.."]
---

What is the capital of Australia? Reply with just the city name.
