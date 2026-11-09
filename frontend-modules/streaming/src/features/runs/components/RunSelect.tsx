import { Group, Select, Text } from "@mantine/core";
import type { RunSummary } from "../../../api/streaming";
import { formatTime } from "../lib/format";
import { RunStateBadge } from "./RunStateBadge";

type RunSelectProps = {
  runs: RunSummary[];
  selected: RunSummary | undefined;
  onSelect: (id: string) => void;
};

/** Picks one of the session's runs, newest first. */
export function RunSelect({ runs, selected, onSelect }: RunSelectProps) {
  const byId = new Map(runs.map((run) => [run.id, run]));
  return (
    <Select
      aria-label="Run"
      placeholder="No runs yet"
      disabled={runs.length === 0}
      data={runs.map((run) => ({ value: run.id, label: run.name }))}
      value={selected?.id ?? null}
      allowDeselect={false}
      onChange={(id) => id && onSelect(id)}
      renderOption={({ option }) => {
        const run = byId.get(option.value);
        return (
          run && (
            <Group justify="space-between" wrap="nowrap" w="100%">
              <Text size="sm">{run.name}</Text>
              <Group gap={6} wrap="nowrap">
                <Text size="xs" c="dimmed">
                  {formatTime(run.created_at)}
                </Text>
                <RunStateBadge state={run.state} />
              </Group>
            </Group>
          )
        );
      }}
      comboboxProps={{ width: 480, position: "bottom-start" }}
      flex={1}
      miw={160}
      maw={420}
    />
  );
}
