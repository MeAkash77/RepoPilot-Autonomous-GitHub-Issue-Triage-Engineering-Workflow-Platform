# ADR-001: pgvector in Postgres over a dedicated vector DB

**Status:** accepted
**Date:** 2026-06-13

## Context

RepoPilot needs dense retrieval over repo knowledge (issues, PRs, docs, code) plus relational state (repos, runs, actions) and full-text search. Options: Pinecone/Qdrant/Weaviate alongside Postgres, or pgvector inside the one Postgres we already need.

## Decision

Single Neon Postgres with pgvector (HNSW, cosine) + native tsvector full-text. Hybrid search is two SQL queries fused with RRF in application code.

## Tradeoffs

- Gain: one database — one backup story, transactional consistency between chunks and their documents (chunk delete cascades can't orphan), joins between vectors and relational metadata in one query, zero extra infra cost, full-text and dense search co-located for hybrid retrieval.
- Give up: raw ANN throughput and recall tuning of dedicated engines; pgvector HNSW build is memory-hungry on large corpora; no built-in sharding.
- Scale honesty: per-repo corpora here are ~10³–10⁴ chunks. pgvector handles 10⁶+ comfortably; we are three orders of magnitude under the ceiling.
- Revisit if: corpus grows past ~5M vectors, or p95 retrieval latency exceeds budget with tuned `hnsw.ef_search`.
