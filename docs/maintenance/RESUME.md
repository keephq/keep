# Site24x7 contribution review

2026-11-01. This repository is a fork of keephq/keep. Preserve the upstream README, license and attribution. The user's contribution is upstream PR https://github.com/keephq/keep/pull/6201 on branch `fix/site24x7-status-and-tags`; it was open when reviewed.

This follow-up uses `maintenance/site24x7-input-validation`, based on that contribution branch. It must be reviewed against `fix/site24x7-status-and-tags`, not main. Do not update the upstream PR or submit messages to upstream maintainers without authorization.

## Findings and change

The existing formatter passed dictionary tags directly to AlertDto and emitted an empty label name for inputs such as `:value`. Tag parsing now lives in a dependency-free helper, copies dictionary inputs and ignores empty keys. Valid existing key/value and bare tags retain their behavior, including first-colon splitting and last-value-wins duplicate names. The mapping copy is shallow; nested values are not modified or deep-copied.

Ten focused unittest cases cover these behaviors. Run:

```sh
python -m unittest discover -s tests/providers/site24x7_provider -p test_tag_parser.py -v
```

The added workflow checks Python 3.11–3.13. These checks validate parsing only, not the full provider, AlertDto validation or external Site24x7 requests.

## Verification

The original 16 formatter tests and the two new edge cases all passed with the real locked Keep dependencies in a dedicated Python 3.11 GitHub Actions job: 18 passed. The ten parser tests also passed on Python 3.11, 3.12 and 3.13.

Evidence: https://github.com/Spirax-M1/keep/actions/runs/41338441789.

The local PC uses Python 3.14, outside Keep's >=3.11,<3.14 range, and lacks pytest and several service dependencies. Full formatter verification therefore ran in CI, not on the local machine. The parser suite and syntax checks also pass locally.

## Remaining upstream checks

The inherited Unit Tests workflow stops at a repository-wide Ruff check (3,482 diagnostics), before installing dependencies or executing tests; diagnostics include unchanged upstream files. The inherited PR policy also requires a linked issue. The dedicated formatter job verifies this change without claiming that all application-wide CI is passing.

The upstream PR remains open and unchanged. Confirm real webhook payload examples and review this follow-up before proposing it upstream. No external request/authentication behavior was changed or tested.
