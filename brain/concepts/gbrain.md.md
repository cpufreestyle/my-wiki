---
type: concepts
title: GBrain
created: '2026-07-02T00:00:00.000Z'
tags:
  - AI
  - brain
  - knowledge-management
---

# GBrain

Personal knowledge brain system integrated with OpenClaw.

## Overview

GBrain is a personal knowledge management system that:
- Stores knowledge in structured markdown files (`/Users/a1-6/brain`)
- Provides semantic search (vector + keyword hybrid)
- Auto-captures signals from conversations (via signal-detector skill)
- Runs nightly maintenance (Dream Cycle cron job)

## Key Features

- **Signal Detection**: Captures entities and ideas from conversations
- **Brain-First Lookup**: Check brain before external APIs
- **Back-linking**: Automatic cross-references between pages
- **Embeddings**: Local Ollama (nomic-embed-text) for vector search
- **Dream Cycle**: Nightly maintenance (lint, sync, embed, orphans, purge)

## Integration with OpenClaw

- GBrain dispatch instructions in system prompt (MANDATORY)
- signal-detector skill fires on every message (should fire...)
- brain-ops skill for read/write operations

## Current Status (2026-07-02)

- Dream Cycle cron: ✅ Running successfully
- Brain content: ❌ Almost empty (signal-detector not executing)
- gbrain CLI: ✅ Working
- Next step: Fix signal-detector execution

[Source: User, 2026-07-02]
