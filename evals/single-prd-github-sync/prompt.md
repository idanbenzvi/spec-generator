---
tags: [spec-generator]
max_turns: 80
timeout_seconds: 1800
allowed_tools: [Read, Glob, Grep, Skill, Write, Edit, Bash, WebFetch, WebSearch]
---

here's our PRD: we want a nightly job that pulls all open issues labeled 'customer' from our GitHub org repos and posts a digest to a Slack channel. spec it out — use the web as source.
