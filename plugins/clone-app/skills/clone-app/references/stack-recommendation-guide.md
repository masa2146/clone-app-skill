# Stack Recommendation Guide (Phase 4)

Goal: present the user 2-3 concrete stack options for building the clone, then
let them pick. The pick locks effort + cost math in Phase 5.

## Inputs you have
- Detected original framework (from RE fingerprint): Native Kotlin/Java, Flutter, React Native, etc.
- Detected HTTP stack + backend signals (Retrofit/Ktor/Apollo/GraphQL/WebSocket).
- Feature surface (screen count, SDKs, permissions).

## How to choose the 2-3 options
Always include:
1. **Fastest for AI-assisted dev** — default to **Flutter** (single codebase, strong AI codegen, fast UI) unless the app is heavily native-platform-dependent.
2. **JS-ecosystem option** — **React Native + Expo** when the team is JS-leaning or web reuse matters.
3. **Match-the-original** — only when the original's nativeness is essential (deep platform APIs, AR, heavy native SDKs). Note the higher effort.

## Backend
- If RE shows first-party API hosts → a backend is required. Recommend **Node/TS (NestJS or Express)** or **Supabase** (fastest with AI) unless GraphQL detected → recommend **Apollo Server** or **Hasura**.
- If only third-party hosts (Firebase, payment SDKs) → likely **BaaS / no custom backend**; note it.

## Output format to the user
Present a short table: Option | Mobile stack | Backend | Why | Relative effort (Low/Med/High).
Then ask: "Which stack should I base the effort + cost estimate on?"
