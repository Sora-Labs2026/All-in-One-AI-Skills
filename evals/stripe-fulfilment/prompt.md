---
description: Reliable Stripe Checkout fulfilment through verified, idempotent webhooks
tags: [integrations, core]
runs: 3
max_turns: 15
timeout_seconds: 300
allowed_tools: [Skill, Read, Glob, Grep]
plugins: ["../.."]
---

Our Next.js (App Router) app uses Stripe Checkout. After payment I need to give the user a `pro` role in our Postgres database. How should I implement fulfilment so that it is reliable? Outline the code.
