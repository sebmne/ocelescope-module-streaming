import { useQueryClient } from "@tanstack/react-query";
import { getListRunsQueryKey, useCancelRun, useListRuns } from "../../../api/streaming";
import { isActive } from "../lib/runState";

/** How often the run list is refreshed while a run is active. */
const POLL_INTERVAL_MS = 1000;

/** The session's runs, refreshed while any of them is pending or running. */
export function useRuns() {
  return useListRuns({
    query: {
      refetchInterval: (query) => (query.state.data?.some((run) => isActive(run.state)) ? POLL_INTERVAL_MS : false),
    },
  });
}

/** Cancels a run and refreshes the run list. */
export function useCancelRunAndRefresh() {
  const queryClient = useQueryClient();
  return useCancelRun({
    mutation: {
      onSettled: () => queryClient.invalidateQueries({ queryKey: getListRunsQueryKey() }),
    },
  });
}
