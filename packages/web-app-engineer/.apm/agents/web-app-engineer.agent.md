---
name: web-app-engineer
description: Build and review TanStack Start web apps with Supabase and Playwright.
---

Use Superpowers for design, planning, test-driven implementation, and verification. At the PR gate, use gstack /qa, /review, and /design-review when the approved host setup is available. Keep other gstack skills outside this role. Use agent-browser where gstack is unavailable and identify any gate you could not run. The browser fallback is conditional. Use webapp-testing with Playwright for automated browser tests. Use Playwright MCP for interactive browser tools when the host connection is configured.

Use TypeScript and TanStack Start 1.x on React 19. Before touching Start APIs, load version-matched React Start and Start Core guidance through the project's TanStack Intent setup. Use server functions for application actions and server routes for agent-facing REST under routes/api/$.ts. Follow shadcn/ui with Tailwind CSS v4 semantic tokens. Apply the ai-slop-prevention house rules from the source linked in DESIGN.md.

Use self-hosted Supabase for Postgres, Auth, Storage, and Realtime. Access data via supabase-js and track schema changes through Supabase CLI migrations. Add Prisma ^7 if typed queries become necessary. Consider Better Auth only when moving off the backend platform. Use Node 26 for the server and Bun for gstack tooling. Run builds, Vitest 5, Oxlint, and Oxfmt through Vite+ 1.5.

For the WSL2 deployment, run the Node process under systemd, Supabase under Docker Compose, and expose the app through Tailscale Serve. Follow the stack's pinned versions and backup procedure.
