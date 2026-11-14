import { useQueryClient } from "@tanstack/react-query";
import {
  getListRunsQueryKey,
  type RunSummary,
  useCancelRun,
  useDeleteRun,
  useListRuns,
  useStartRun,
} from "../api/streaming";

const POLL_MS = 500;

export const isActive = ({ state }: RunSummary) => state === "PENDING" || state === "STARTED";

/** The runs on `ocelId`, newest first; polled while one of them is active. */
export function useRuns(ocelId: string | null) {
  return useListRuns({
    query: {
      select: (runs) => runs.filter((run) => run.ocel_id === ocelId),
      refetchInterval: ({ state }) => (state.data?.some(isActive) ? POLL_MS : false),
    },
  });
}

/** Start, cancel and delete; each refreshes the run list. */
export function useRunActions() {
  const queryClient = useQueryClient();
  const mutation = { onSettled: () => queryClient.invalidateQueries({ queryKey: getListRunsQueryKey() }) };
  return { start: useStartRun({ mutation }), cancel: useCancelRun({ mutation }), remove: useDeleteRun({ mutation }) };
}
