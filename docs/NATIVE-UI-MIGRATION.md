# Native desktop migration

## Current production boundary

The current Windows/Linux shell uses Tauri, a WebView, and an authenticated local Python worker. It is not a WebView-free native UI. NSIS changes installation, not rendering.

## Proposed target

A separate native Qt Widgets C++ frontend is the initial implementation candidate, using native widgets and a virtualized table model, with the current SQLite and registry services preserved behind a narrow, authenticated worker interface. Evaluate Qt deployment, dependency licensing and packaging before adopting it. A Rust/Slint alternative remains possible if the native UI and distribution requirements are met. Do not mix engines in the production package or replace a working UI with a partial prototype.

## Migration acceptance

1. Preserve existing workspace paths and database schema compatibility, secure credential storage and all backup/restore guarantees.
2. Implement all seven existing screens and company profiles, then mail; use real worker responses, no fixtures in production.
3. No browser runtime, no WebView dependency, no HTML/JS renderer. Run UI work only on its native event loop; cancel obsolete background requests.
4. Croatian-only dark theme, a single navigation hierarchy, keyboard accessibility and window resizing.
5. Native UI tests, crash/restart tests, memory/CPU benchmarks on both platforms and full registry acceptance.
6. Only switch the release pipeline after full feature parity and measured stability. Keep existing installer identity and data paths.

## Secure updates

The new update verification module accepts only signed Ed25519 manifests from an independently trusted public key, rejects downgrade/edition mismatch, and streams package hashes. It does not download or execute updates. Production integration needs a protected signing key, pinned public key, authenticated release acquisition, staged installation with backup, rollback and separate Windows/Linux acceptance. No automatic execution of unsigned packages.
