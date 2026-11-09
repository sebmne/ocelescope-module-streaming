import { Group, NumberInput, Paper, Select, Stack, Text } from "@mantine/core";
import type { BufferInfo, HeuristicInfo } from "../../../api/streaming";
import { SchemaForm } from "../../../components/SchemaForm";
import { BUFFER_MODES, type BufferFormState, type BufferMode, hasCapacity, heuristicsFor } from "../model";

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
          Everything the algorithm remembers is stored in buffers. Choose per buffer whether and how its entries are
          evicted.
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
  const candidates = heuristicsFor(heuristics, value.mode);
  const heuristic = candidates.find((candidate) => candidate.key === value.heuristic);
  const availableModes = BUFFER_MODES.filter(
    (mode) => mode.value === "unbounded" || heuristicsFor(heuristics, mode.value).length > 0,
  );

  const setMode = (mode: BufferMode) => {
    const keep = heuristicsFor(heuristics, mode).some((candidate) => candidate.key === value.heuristic);
    const first = heuristicsFor(heuristics, mode)[0]?.key ?? null;
    onChange(keep ? { mode } : { mode, heuristic: first, heuristicParams: {} });
  };

  return (
    <Paper withBorder p="sm" radius="sm">
      <Stack gap="xs">
        <div>
          <Text size="sm" fw={500}>
            {buffer.label}
          </Text>
          <Text size="xs" c="dimmed">
            {buffer.description}
          </Text>
        </div>
        <Select
          label="Eviction"
          size="xs"
          data={availableModes.map((mode) => ({ value: mode.value, label: mode.label }))}
          value={value.mode}
          allowDeselect={false}
          onChange={(mode) => mode && setMode(mode as BufferMode)}
        />
        {value.mode !== "unbounded" && (
          <>
            <Group grow gap="xs" align="flex-start">
              {hasCapacity(value.mode) && (
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
              )}
              <Select
                label="Heuristic"
                size="xs"
                data={candidates.map((candidate) => ({ value: candidate.key, label: candidate.label }))}
                value={heuristic ? heuristic.key : null}
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
