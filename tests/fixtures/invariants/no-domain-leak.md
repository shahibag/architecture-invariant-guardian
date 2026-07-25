---
id: no-domain-leak
title: No internal domain or persistence leakage
severity: error
scope:
  languages: [java]
  include_paths: ["src/main/java/**"]
---

## Rule

Public boundaries must not expose persistence entities or internal aggregates.

## Rationale

Leaking implementation types makes callers depend on internal structure.

## Violating examples

A public controller method returning an OrderEntity.

## Acceptable examples

A public controller method returning an OrderResponse DTO.

