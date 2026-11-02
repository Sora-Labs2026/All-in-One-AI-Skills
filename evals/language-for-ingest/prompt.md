---
description: Gives an honest language recommendation for a new high-throughput service
tags: [routing, core]
runs: 3
max_turns: 15
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
plugins: ["../.."]
---

We're starting a new service that ingests about 200k events per second, parses them and writes aggregates to ClickHouse. The language isn't decided; the team knows Python and Go. What should we use?
