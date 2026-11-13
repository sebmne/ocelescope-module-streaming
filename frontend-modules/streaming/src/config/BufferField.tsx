import { Group, NumberInput, Paper, Select, Stack, Switch, Text } from "@mantine/core";
import type { HeuristicInfo } from "../api/streaming";
import { ParamFields } from "./ParamFields";
import type { BufferState } from "./useConfig";

type BufferFieldProps = {
  name: string;
  value: BufferState;
  heuristics: HeuristicInfo[];
  onChange: (patch: Partial<BufferState>) => void;
};

/** One buffer: unbounded, or bounded by a capacity and a heuristic. */
export function BufferField({ name, value, heuristics, onChange }: BufferFieldProps) {
  const heuristic = heuristics.find((candidate) => candidate.key === value.heuristic);
  return (
    <Paper withBorder p="xs">
      <Stack gap={6}>
        <Group justify="space-between">
          <Text size="sm" fw={500} tt="capitalize">
            {name}
          </Text>
          <Switch
            size="xs"
            label={value.bounded ? "Bounded" : "Unbounded"}
            labelPosition="left"
            checked={value.bounded}
            onChange={(event) => onChange({ bounded: event.currentTarget.checked })}
          />
        </Group>
        {value.bounded && (
          <>
            <Group grow gap="xs">
              <NumberInput
                size="xs"
                label="Capacity"
                min={0}
                allowDecimal={false}
                value={value.capacity}
                onChange={(capacity) => typeof capacity === "number" && onChange({ capacity })}
              />
              <Select
                size="xs"
                label="Heuristic"
                allowDeselect={false}
                data={heuristics.map(({ key, label }) => ({ value: key, label }))}
                value={value.heuristic}
                onChange={(key) => key && onChange({ heuristic: key, params: {} })}
              />
            </Group>
            {heuristic && (
              <>
                <Text size="xs" c="dimmed">
                  {heuristic.description}
                </Text>
                <ParamFields schema={heuristic.params} value={value.params} onChange={(params) => onChange({ params })} />
              </>
            )}
          </>
        )}
      </Stack>
    </Paper>
  );
}
