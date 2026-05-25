# Cross-Batch Merge Notes (delete on final merge)

These conflicts are expected when batches land in sequence. Resolution intent:

- **L3 (SBOM/provenance attestations) vs M7 (drop unused workflow perms):**
  L3 re-adds `id-token: write` and `attestations: write` to the docker-publish
  workflow that M7 removed. Keep them when L3 lands — they are required by the
  attestation step. M7's intent (no unused perms) is preserved because L3 makes
  them used.

- **L4 (pin compose image to `1.2`) vs M5 (bind compose port to localhost):**
  Both edit `docker-compose.yml`. Take both changes: pinned image tag AND the
  `127.0.0.1:8430:80` port binding.

- **L7 (sanitize group names) + L8 (fail loud on bad regex) vs M6 (Outline
  pagination cap):** All three touch `src/helpers/outline.py`. Each lives in a
  distinct function; resolve by accepting all three hunks.

- **L5 folded into another commit:** Acknowledged NIT, not fixed — no dedicated
  commit for L5 but the change is present in the branch.
