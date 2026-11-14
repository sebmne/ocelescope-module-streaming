import { useQueryClient } from "@tanstack/react-query";
import { useEffect } from "react";
import {
  getListRunsQueryKey,
  type RunSummary,
  useCancelRun,
  useDeleteRun,
  useGetRunFrame,
  useGetRunLayout,
  useListRuns,
  useSetRunPace,
  useStartRun,
  useStepRun,
} from "../api/streaming";

const RUNS_MS = 500;
const FRAME_MS = 100;

export const isActive = ({ state }: RunSummary) => state === "PENDING" || state === "STARTED";

/** The runs on `ocelId`, newest first; polled while one of them is active. */
export function useRuns(ocelId: string | null) {
  return useListRuns({
    query: {
      select: (runs) => runs.filter((run) => run.ocel_id === ocelId),
      refetchInterval: ({ state }) => (state.data?.some(isActive) ? RUNS_MS : false),
    },
  });
}

/** The run's latest model frame; polled while it is active and fetched once more when it ends. */
export function useFrame(run: RunSummary | undefined) {
  const active = run !== undefined && isActive(run);
  const frame = useGetRunFrame(run?.id ?? "", {
    query: { enabled: run !== undefined, refetchInterval: active ? FRAME_MS : false },
  });
  const { refetch } = frame;
  useEffect(() => {
    if (run && !active) refetch();
  }, [run, active, refetch]);
  return frame;
}

/** The run's fixed layout, fetched once its first pass is done; empty without one. */
export function useLayout(run: RunSummary | undefined) {
  return useGetRunLayout(run?.id ?? "", {
    query: { enabled: run !== undefined && run.phase === "replay", staleTime: Number.POSITIVE_INFINITY },
  });
}

/** Start, steer, cancel and delete; each refreshes the run list. */
export function useRunActions() {
  const queryClient = useQueryClient();
  const mutation = { onSettled: () => queryClient.invalidateQueries({ queryKey: getListRunsQueryKey() }) };
  return {
    start: useStartRun({ mutation }),
    pace: useSetRunPace({ mutation }),
    step: useStepRun({ mutation }),
    cancel: useCancelRun({ mutation }),
    remove: useDeleteRun({ mutation }),
  };
}
