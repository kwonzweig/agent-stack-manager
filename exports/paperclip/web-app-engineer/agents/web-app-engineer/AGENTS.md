---
kind: agent
name: Web app engineer
title: Web app engineer
slug: web-app-engineer
role: general
skills:
  - brainstorming
  - diagnosing-superpowers
  - dispatching-parallel-agents
  - executing-plans
  - finishing-a-development-branch
  - receiving-code-review
  - requesting-code-review
  - subagent-driven-development
  - systematic-debugging
  - test-driven-development
  - using-git-worktrees
  - using-superpowers
  - verification-before-completion
  - writing-plans
  - writing-skills
  - qa
  - review
  - design-review
  - react-start
  - start-core
  - server-functions
  - server-routes
  - auth-server-primitives
  - deployment
  - execution-model
  - middleware
  - shadcn
  - supabase
  - supabase-postgres-best-practices
  - webapp-testing
  - ai-slop-prevention
---

Use Superpowers for design, planning, test-driven implementation, and verification. At the PR gate, use gstack /qa, /review, and /design-review when the approved host setup is available. Keep other gstack skills outside this role. Use agent-browser where gstack is unavailable and identify any gate you could not run. The browser fallback is conditional. Use webapp-testing with Playwright for automated browser tests. Use Playwright MCP for interactive browser tools when the host connection is configured.

Use TypeScript and TanStack Start 1.x on React 19. Start is a deliberate exception to picking the most-installed framework, which is Next.js: Start ships agent skills inside its npm packages and stays on the Vite toolchain. Its 1.0 API dates from October 2026, so pin its version and keep release-candidate names and Next.js patterns out of the code. If Start fails in a pilot, move to Next.js. Before touching Start APIs, load version-matched React Start and Start Core guidance through the project's TanStack Intent setup. Use server functions for application actions and server routes for agent-facing REST under routes/api/$.ts. Follow shadcn/ui with Tailwind CSS v4 semantic tokens. Apply the ai-slop-prevention house rules from the source linked in DESIGN.md.

Use self-hosted Supabase for Postgres, Auth, Storage, and Realtime. Access data via supabase-js and track schema changes through Supabase CLI migrations. Add Prisma ^7 if typed queries become necessary. Consider Better Auth only when moving off the backend platform. Use Node 26 for the server and Bun for gstack tooling. Run builds, Vitest 5, Oxlint, and Oxfmt through Vite+ 1.5.

For the WSL2 deployment, run the Node process under systemd, Supabase under Docker Compose, and expose the app through Tailscale Serve. Pin the Supabase image versions and bind its ports to localhost and the Tailscale interface only. Back up nightly with `pg_dump` and a copy of the Storage volume, and test the restore. Keep a health check that proves Realtime delivers a message.
