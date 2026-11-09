import type { RunSummary } from "../../../api/streaming";

/** Progress of a run in percent, 0 if the total is unknown. */
export function progressPercent(run: RunSummary): number {
  const { processed = 0, total } = run.progress;
  return total ? Math.min(100, (processed / total) * 100) : 0;
}
