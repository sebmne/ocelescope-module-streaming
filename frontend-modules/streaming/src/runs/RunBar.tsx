import { ActionIcon, Badge, Group, SegmentedControl, Select, Tooltip } from "@mantine/core";
import { SettingsIcon, SquareIcon } from "lucide-react";
import type { RunSummary } from "../api/streaming";
import { isActive, useCancel } from "./useRuns";

export type View = "model" | "reference" | "both";

const STATE_COLORS: Record<string, string> = { STARTED: "blue", SUCCESS: "green", FAILURE: "red", CANCELLED: "orange" };

type RunBarProps = {
  runs: RunSummary[];
  run: RunSummary | undefined;
  onSelect: (id: string) => void;
  view: View;
  onView: (view: View) => void;
  onToggleSettings: () => void;
};

/** Run selection and state on the left, view controls on the right. */
export function RunBar({ runs, run, onSelect, view, onView, onToggleSettings }: RunBarProps) {
  const cancel = useCancel();
  return (
    <Group px="sm" py="xs" justify="space-between" wrap="nowrap" style={{ borderBottom: "2px solid var(--mantine-color-default-border)" }}>
      <Group gap="xs" wrap="nowrap" flex={1} miw={0}>
        <Select
          aria-label="Run"
          placeholder="No runs yet"
          disabled={runs.length === 0}
          allowDeselect={false}
          data={runs.map(({ id, name }) => ({ value: id, label: name }))}
          value={run?.id ?? null}
          onChange={(id) => id && onSelect(id)}
          flex={1}
          maw={420}
        />
        {run && <Badge color={STATE_COLORS[run.state] ?? "gray"} variant="light">{run.state.toLowerCase()}</Badge>}
        {run && isActive(run.state) && (
          <Tooltip label="Cancel run">
            <ActionIcon variant="light" color="red" size="input-sm" aria-label="Cancel run" onClick={() => cancel.mutate({ runId: run.id })}>
              <SquareIcon size={16} />
            </ActionIcon>
          </Tooltip>
        )}
      </Group>
      <Group gap="xs" wrap="nowrap">
        <SegmentedControl
          size="xs"
          disabled={!run?.model_id}
          value={view}
          onChange={(value) => onView(value as View)}
          data={[
            { value: "model", label: "Streaming" },
            { value: "reference", label: "Offline" },
            { value: "both", label: "Side by side" },
          ]}
        />
        <Tooltip label="Toggle settings">
          <ActionIcon variant="outline" size="input-sm" aria-label="Toggle settings" onClick={onToggleSettings}>
            <SettingsIcon size={20} />
          </ActionIcon>
        </Tooltip>
      </Group>
    </Group>
  );
}
