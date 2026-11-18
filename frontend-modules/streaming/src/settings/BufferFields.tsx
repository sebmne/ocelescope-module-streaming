import { Divider, NumberInput, Select, Stack, Text } from "@mantine/core";
import type { AlgorithmInfo, BufferBound, HeuristicInfo } from "../api/streaming";
import { defaults, type Values } from "./schema";
import { SettingsFields } from "./SettingsFields";

/** A buffer's settings; without a capacity, the buffer is unbounded. */
export type BufferValues = { capacity?: number; heuristic: string; parameters: Values };

type Props = {
  algorithm: AlgorithmInfo;
  heuristics: HeuristicInfo[];
  values: Record<string, BufferValues>;
  onChange: (values: Record<string, BufferValues>) => void;
};

export const bufferDefaults = (heuristics: HeuristicInfo[], heuristic = "lru"): BufferValues => ({
  heuristic,
  parameters: defaults(heuristics.find(({ key }) => key === heuristic)?.parameters_schema ?? {}),
});

/** The bounded buffers of a run, as sent to the API. */
export const bounds = (values: Record<string, BufferValues>): Record<string, BufferBound> =>
  Object.fromEntries(
    Object.entries(values).flatMap(([key, { capacity, heuristic, parameters }]) =>
      capacity === undefined ? [] : [[key, { capacity, heuristic, parameters }]],
    ),
  );

/** Capacity and heuristic per buffer, in eviction order; sinks are always unbounded. */
export function BufferFields({ algorithm, heuristics, values, onChange }: Props) {
  const label = (key: string) => heuristics.find((heuristic) => heuristic.key === key)?.label ?? key;
  return (
    <Stack gap="lg">
      {algorithm.buffers
        .filter(({ sink }) => !sink)
        .map((buffer) => {
          const value = values[buffer.key] ?? bufferDefaults(heuristics);
          const set = (next: BufferValues) => onChange({ ...values, [buffer.key]: next });
          const schema = heuristics.find(({ key }) => key === value.heuristic)?.parameters_schema ?? {};
          return (
            <Stack key={buffer.key} gap="sm">
              <Divider label={buffer.label} labelPosition="left" />
              <NumberInput
                label="Capacity"
                placeholder="Unbounded"
                min={1}
                allowDecimal={false}
                value={value.capacity ?? ""}
                onChange={(next) => set({ ...value, capacity: typeof next === "number" ? next : undefined })}
              />
              {value.capacity !== undefined && (
                <>
                  <Select
                    label="Heuristic"
                    data={buffer.heuristics.map((key) => ({ value: key, label: label(key) }))}
                    value={value.heuristic}
                    allowDeselect={false}
                    onChange={(next) => next && set({ ...bufferDefaults(heuristics, next), capacity: value.capacity })}
                  />
                  <SettingsFields
                    schema={schema}
                    values={value.parameters}
                    onChange={(parameters) => set({ ...value, parameters })}
                  />
                </>
              )}
            </Stack>
          );
        })}
      {algorithm.buffers.some(({ sink }) => sink) && (
        <Text size="xs" c="dimmed">
          {algorithm.buffers
            .filter(({ sink }) => sink)
            .map(({ label }) => label)
            .join(", ")}{" "}
          only receive what evictions record, so they stay unbounded.
        </Text>
      )}
    </Stack>
  );
}
