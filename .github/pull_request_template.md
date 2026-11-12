<!--
Thanks for contributing! Pull requests go to the `integration` branch, not `main`.
Please read integration.md if you haven't. Delete any section that doesn't apply.
-->

## Summary
<!-- What does this change and why? One or two sentences. -->

## Related issue
<!-- Fixes #123 / Refs #123 -->

## Type of change
- [ ] `fix`: bug fix
- [ ] `feat`: new capability
- [ ] `docs`, `test`, `refactor`, `chore`, `perf`

## How I tested it
<!-- Paste the commands and results, and say which new tests fail without this change. -->
```
python -m pytest
python -m pytest -m e2e
```

## Valuation impact (only if numbers change)
<!-- Source or reasoning (link), the new test vector, and a before/after on a real company. Add the `accuracy` label. -->

## Screenshots (only for UI changes)
<!-- Desktop and phone width. -->

## Checklist
- [ ] This PR targets `integration`
- [ ] The PR title follows Conventional Commits (`type: summary`)
- [ ] I wrote a failing test first and it passes now; the full test suite passes
- [ ] No model maths in JavaScript, no hard-coded currency symbols, no `innerHTML` with provider data
- [ ] I updated docs (README, spec) where behaviour changed
- [ ] No secrets, keys or personal paths are included
- [ ] I added labels (type, area, and `accuracy` / `breaking-change` if relevant)
