import { useCallback, useMemo } from "react";
import { useGetCatalog } from "../../../api/streaming";

/** Returns a function mapping a run's buffer name to the label from the catalog. */
export function useBufferLabel(algorithmKey: string) {
  const { data: catalog } = useGetCatalog();
  const labels = useMemo(() => {
    const algorithm = catalog?.algorithms.find((candidate) => candidate.key === algorithmKey);
    return new Map(algorithm?.buffers.map((buffer) => [buffer.name, buffer.label]));
  }, [catalog, algorithmKey]);
  return useCallback((name: string) => labels.get(name) ?? name, [labels]);
}
