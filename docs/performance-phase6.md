# Phase 6: performance engineering, increment 1

Baseline c45b7eff976e80401f6e0ada952346302a24c9a8, Windows, isolated synthetic
workspaces. No national catalogs or user files were benchmarked.

## 100,000 record baseline

Seed 29.282 s; p95 filtered page 5.067 ms, exact MBS 5.154 ms, indexed
phrase 8.363 ms, equivalent substring phrase 148.511 ms, statistics
120.557 ms, filtered in-memory JSON 61.833 ms. Verified backup 545.824 ms;
restored database 2599.281 ms. SQLite integrity and foreign keys passed.

## Targeted optimization

Provider-only counts now start at the indexed origins table, counting
distinct companies and preserving the existence check for each company.
Rows and ordering are unchanged; combined filters keep the previous query.
A 50,000-row exploratory comparison showed that a global IN rewrite would
slow common-provider plus city filters, so it was not adopted.

In a paired test with 100,000 rows, 200 matching companies, 20 measurements
on the same connection:

| Count query | p50 ms | p95 ms |
|---|---:|---:|
| Previous correlated scan | 65.950 | 73.683 |
| Optimized provider-index count | 0.141 | 0.528 |

Both counts equal 200; complete provider page p95 20.192 ms. The speedup
applies to the count SQL statement, not the entire application. No schema
or durability settings were changed. Regression test covers duplicate
origins, absent providers, pagination and combined filters.

## Instrumentation and endurance

Benchmark now also reports Python/SQLite versions, provider query plan,
actual disk-backed JSON export and Python traced allocations (not total
process RSS). At 100,000 records, exporting 1,000 filtered records wrote
479,777 bytes in 353.443 ms, peak traced allocations 1,742,572 bytes.
Backup and restore again passed integrity checks.

Endurance now seeds 25,000 synthetic companies, never the historical CSV.
10-second smoke passed: 547 writes, 588 searches, 239 statistics requests,
321 exports (1,695 operations); 25,100 final records, zero foreign-key
violations, verified recovery. This is not the four-hour acceptance.

The million-record and four-hour workflows now also trigger on changes to
their benchmark scripts in the existing development branch. They remain
separate from ordinary short CI and from the production release gate.
Actual million-record and 14,400-second results, full-export memory,
national catalog performance and native application measurements remain
required.
