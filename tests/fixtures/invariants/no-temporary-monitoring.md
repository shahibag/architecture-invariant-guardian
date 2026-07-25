---
id: no-temporary-monitoring
title: No temporary monitoring or retry loops masking a root-cause fix
severity: error
scope:
  languages: [java]
  include_paths: ["src/main/java/**"]
---

## Rule

Do not add polling or wait-retry loops to mask a missing state transition.

## Rationale

Such loops hide the root cause and create unowned operational load.

## Violating examples

Adding a scheduler that repeatedly checks an order updated by the same change.

## Acceptable examples

A documented daily reconciliation job that is the source of truth for that process.

