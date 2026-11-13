import { useQueryClient } from "@tanstack/react-query";
import { getListRunsQueryKey, type TaskState, useCancelRun, useListRuns } from "../api/streaming";

export const isActive = (state: TaskState) => state === "PENDING" || state === "STARTED";

/** The session's runs, newest first; refreshed every second while one is active. */
export function useRuns() {
  return useListRuns({
    query: { refetchInterval: (query) => (query.state.data?.some((run) => isActive(run.state)) ? 1000 : false) },
  });
}

export function useCancel() {
  const queryClient = useQueryClient();
  return useCancelRun({
    mutation: { onSettled: () => queryClient.invalidateQueries({ queryKey: getListRunsQueryKey() }) },
  });
}
