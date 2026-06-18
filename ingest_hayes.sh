#!/usr/bin/env bash
# Re-ingest Hayes 1972 by ware-section — steps 2 & 3 of the re-ingest.
#
# RUN STEP 1 FIRST (deletes the broken 362 records; backup bundle/catalog.jsonl.bak exists):
#   uv run iaccm forget-source "Hayes_1972_Late Roman Pottery.pdf"
# THEN:
#   bash ingest_hayes.sh
#
# Each segment is its own resumable Batch-API run (~50% cheaper) and writes to the catalog as chunks
# land. printed→PDF offset is +26 (verified at ARS); ARS 39-236 is solid, minor-ware ranges assume
# the offset holds — spot-check one `iaccm show` per section if a range looks off. Excludes the ARS
# decoration/stamp pages (printed 211-302) on purpose.

set -u
cd "$(dirname "$0")"   # run from the repo root so the relative corpus/ path resolves

PDF="corpus/Hayes_1972_Late Roman Pottery.pdf"

run() {  # run() "<ware>" "<pdf-pages>" [extra flags...]
  local ware="$1" pages="$2"; shift 2
  echo
  echo "=================================================================="
  echo "=== $ware  (pp. $pages) ==="
  echo "=================================================================="
  uv run iaccm ingest "$PDF" --source hayes-1972 --ware "$ware" --pages "$pages" --batch "$@" \
    || echo "  ! '$ware' exited non-zero — continuing; re-run this segment later to finish it."
}

# African Red Slip Ware — the bulk; first clean run skips the stale resume sidecar.
run "African Red Slip Ware"          39-236  --no-resume

# Minor wares (one forced --ware each).
run "Tripolitanian Red Slip Ware"    329-335
run "Çandarlı Ware"                  342-348
run "Late Roman C Ware"              349-396
run "Cypriot Red Slip Ware"          397-412
run "Egyptian Red Slip Ware"         413-425
run "Gaulish Terra Sigillata Grise"  426-430
run "Other Late Roman Wares"         431-446

echo
echo "=== Hayes re-ingest complete ==="
