import { TaskState } from "../../../api/streaming";

const ACTIVE: ReadonlySet<TaskState> = new Set([TaskState.PENDING, TaskState.STARTED]);

/** Whether a run in this state may still change. */
export function isActive(state: TaskState): boolean {
  return ACTIVE.has(state);
}

export const STATE_LABEL: Record<TaskState, string> = {
  PENDING: "Pending",
  STARTED: "Running",
  SUCCESS: "Done",
  FAILURE: "Failed",
  SKIPPED: "Skipped",
  CANCELLED: "Cancelled",
};

export const STATE_COLOR: Record<TaskState, string> = {
  PENDING: "gray",
  STARTED: "blue",
  SUCCESS: "green",
  FAILURE: "red",
  SKIPPED: "gray",
  CANCELLED: "orange",
};
