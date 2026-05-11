# Contributing

Thanks for contributing to this project.

## Development Workflow

1. Create a branch from `main`.
2. Make focused changes.
3. Run tests/build locally.
4. Open a pull request with a clear description.

Recommended branch names:
- `feat/<short-name>`
- `fix/<short-name>`
- `docs/<short-name>`
- `chore/<short-name>`

## Commit Message Standard

Use Conventional Commits:

```text
<type>(<scope>): <short summary>

<optional body>
<optional footer>
```

Common types:
- `feat`: new functionality
- `fix`: bug fix
- `docs`: documentation only
- `refactor`: code change without behavior change
- `test`: tests only
- `chore`: tooling/maintenance

Examples:
- `feat(analytics): add field-scoped year filtering`
- `fix(report): correct weekly comparison axis labels`
- `docs(readme): add setup instructions`

Rules:
- Use imperative mood (`add`, `fix`, `update`).
- Keep subject line under ~72 chars when possible.
- One logical change per commit.

## Pull Request Standard

Each PR should include:
- What changed and why
- Risk/impact notes
- How it was tested
- Screenshots for UI changes

Checklist:
- [ ] Build passes
- [ ] Relevant tests pass
- [ ] No secrets added
- [ ] No raw data added
- [ ] Docs updated if behavior changed

Recommended pre-PR check:

```bash
./04_modeling_experimental/scripts/check_quality.sh
```

## Code Standards

Language-specific standards:
- [Python Standards](01_project_docs_notes/docs/standards/python.md)
- [TypeScript Standards](01_project_docs_notes/docs/standards/typescript.md)
- [Repository Standards](01_project_docs_notes/docs/standards/repository.md)

## Security and Sensitive Data

- Do not commit secrets, API keys, tokens, or passwords.
- Do not commit raw datasets under `04_modeling_experimental/data/raw`.
- Review `.gitignore` before staging.
- If sensitive data is committed by mistake, report immediately and rotate credentials.
