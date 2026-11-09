import { Badge } from "@mantine/core";
import type { TaskState } from "../../../api/streaming";
import { STATE_COLOR, STATE_LABEL } from "../lib/runState";

export function RunStateBadge({ state }: { state: TaskState }) {
  return (
    <Badge color={STATE_COLOR[state]} variant="light">
      {STATE_LABEL[state]}
    </Badge>
  );
}
