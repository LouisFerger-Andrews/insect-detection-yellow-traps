# TypeScript Standards

## Target

- TypeScript strict mode for frontend code.
- Prefer explicit types for public interfaces and API payloads.

## Style

- Use functional React components and hooks.
- Keep components focused; extract helpers for repeated logic.
- Use clear prop and state names.
- Avoid `any`; use unions/generics where possible.

## State and Data Flow

- Keep state local unless shared globally.
- Derive values instead of duplicating state.
- Handle loading/error/empty states explicitly.

## API Layer

- Centralize network calls in API client modules.
- Type all request/response payloads.
- Avoid inline fetch logic inside render code.

## UI and Accessibility

- Use semantic HTML where possible.
- Label form controls.
- Keep chart labels/units explicit.

## Recommended Tooling

Recommended industry baseline:
- ESLint (TypeScript + React rules)
- Prettier for formatting
- `tsc --noEmit` for type validation

Example commands:

```bash
npm run build
# or
tsc --noEmit
```

