import { Group, NumberInput, Paper, Select, Stack, Switch, Text, Tooltip } from "@mantine/core";
import type { BufferInfo, HeuristicInfo } from "../../../api/streaming";
import { SchemaForm } from "../../../components/SchemaForm";
import type { BufferFormState } from "../model";

type BufferListProps = {
  buffers: BufferInfo[];
  heuristics: HeuristicInfo[];
  values: Record<string, BufferFormState>;
  onChange: (buffer: string, patch: Partial<BufferFormState>) => void;
};

export function BufferList({ buffers, heuristics, values, onChange }: BufferListProps) {
  return (
    <Stack gap="xs">
      <div>
        <Text size="sm" fw={500}>
          Buffers
        </Text>
        <Text size="xs" c="dimmed">
          Bound a buffer to limit its memory. When it is full, the heuristic decides which entry to evict.
        </Text>
      </div>
      {buffers.map((buffer) => (
        <BufferCard
          key={buffer.name}
          buffer={buffer}
          heuristics={heuristics}
          value={values[buffer.name]}
          onChange={(patch) => onChange(buffer.name, patch)}
        />
      ))}
    </Stack>
  );
}

type BufferCardProps = {
  buffer: BufferInfo;
  heuristics: HeuristicInfo[];
  value: BufferFormState;
  onChange: (patch: Partial<BufferFormState>) => void;
};

function BufferCard({ buffer, heuristics, value, onChange }: BufferCardProps) {
  const heuristic = heuristics.find((candidate) => candidate.key === value.heuristic);

  const setBounded = (bounded: boolean) =>
    onChange(bounded && value.heuristic === null ? { bounded, heuristic: heuristics[0]?.key ?? null } : { bounded });

  return (
    <Paper withBorder p="sm" radius="sm">
      <Stack gap="xs">
        <div>
          <Group justify="space-between" wrap="nowrap">
            <Text size="sm" fw={500}>
              {buffer.label}
            </Text>
            <Tooltip label={value.bounded ? "Bounded" : "Unbounded"}>
              <Switch
                aria-label={`Bound ${buffer.label}`}
                size="xs"
                checked={value.bounded}
                onChange={(event) => setBounded(event.currentTarget.checked)}
              />
            </Tooltip>
          </Group>
          <Text size="xs" c="dimmed">
            {buffer.description}
          </Text>
        </div>
        {value.bounded && (
          <>
            <Group grow gap="xs" align="flex-start">
              <NumberInput
                label="Capacity"
                size="xs"
                value={value.capacity}
                min={0}
                step={100}
                allowDecimal={false}
                thousandSeparator=" "
                onChange={(capacity) => typeof capacity === "number" && onChange({ capacity })}
              />
              <Select
                label="Heuristic"
                size="xs"
                data={heuristics.map((candidate) => ({ value: candidate.key, label: candidate.label }))}
                value={value.heuristic}
                allowDeselect={false}
                onChange={(key) => onChange({ heuristic: key, heuristicParams: {} })}
              />
            </Group>
            {heuristic && (
              <>
                <Text size="xs" c="dimmed">
                  {heuristic.description}
                </Text>
                <SchemaForm
                  schema={heuristic.params_schema}
                  value={value.heuristicParams}
                  onChange={(heuristicParams) => onChange({ heuristicParams })}
                />
              </>
            )}
          </>
        )}
      </Stack>
    </Paper>
  );
}
