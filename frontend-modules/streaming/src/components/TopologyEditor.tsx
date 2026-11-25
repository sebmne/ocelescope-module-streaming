import { Badge, Box, Group, NumberInput, Paper, Select, Stack, Text, Tooltip } from "@mantine/core";
import type { AlgorithmInfo, BufferConfig, BufferInfo, Catalog } from "../api/streaming";
import { bufferMemory, findHeuristic, formatCount, heuristicParams } from "../lib/config";
import { ParamsFields } from "./ParamsFields";

type TopologyEditorProps = {
  catalog: Catalog;
  algorithm: AlgorithmInfo;
  buffers: Record<string, BufferConfig>;
  onChange: (name: string, config: BufferConfig) => void;
  disabled?: boolean;
};

/**
 * The buffer topology of an algorithm, drawn like the framework figure of the paper: an item
 * enters `upd`, which inserts into the buffers; `emit` reads the buffers that hold the model.
 * Each buffer shows its capacity, its heuristic and the heuristic's private buffers, and all of
 * them can be edited here.
 */
export function TopologyEditor({ catalog, algorithm, buffers, onChange, disabled }: TopologyEditorProps) {
  return (
    <Stack align="center" gap={0} p="md">
      <Group gap={0} wrap="nowrap">
        <Node label="item sᵢ" round />
        <Arrow />
        <Node label="upd" detail={algorithm.label} />
      </Group>
      <Arrow label="ins" both vertical />
      <Group gap="sm" justify="center" align="stretch">
        {algorithm.buffers.map((info) => (
          <BufferCard
            key={info.name}
            catalog={catalog}
            info={info}
            config={buffers[info.name] ?? { capacity: info.default_capacity, heuristic: { name: "fifo", params: {} } }}
            onChange={(config) => onChange(info.name, config)}
            disabled={disabled}
          />
        ))}
      </Group>
      <Arrow label="read" vertical />
      <Group gap={0} wrap="nowrap">
        <Node label="emit" detail="reads the highlighted buffers" />
        <Arrow />
        <Node label={algorithm.model_label} round />
      </Group>
    </Stack>
  );
}

function Node({ label, detail, round }: { label: string; detail?: string; round?: boolean }) {
  return (
    <Paper
      withBorder
      px="md"
      py="sm"
      radius={round ? "xl" : "md"}
      bg={round ? "var(--mantine-color-default-hover)" : undefined}
      style={{ flexShrink: 0, textAlign: "center" }}
    >
      <Text fw={600} size="sm" ff={round ? undefined : "monospace"}>
        {label}
      </Text>
      {detail && (
        <Text size="xs" c="dimmed" maw={120}>
          {detail}
        </Text>
      )}
    </Paper>
  );
}

function Arrow({ label, both, vertical }: { label?: string; both?: boolean; vertical?: boolean }) {
  if (vertical) {
    return (
      <Group gap={6} py={4} wrap="nowrap">
        <svg width="12" height="36" viewBox="0 0 12 36" aria-hidden>
          <line x1="6" y1={both ? 6 : 2} x2="6" y2="30" stroke="var(--mantine-color-dimmed)" strokeWidth="1.5" />
          <path d="M2 28 L6 34 L10 28" fill="none" stroke="var(--mantine-color-dimmed)" strokeWidth="1.5" />
          {both && <path d="M2 8 L6 2 L10 8" fill="none" stroke="var(--mantine-color-dimmed)" strokeWidth="1.5" />}
        </svg>
        <Text size="10px" c="dimmed" ff="monospace">
          {label}
        </Text>
      </Group>
    );
  }
  return (
    <Stack gap={0} align="center" px={4} style={{ flexShrink: 0 }}>
      <Text size="10px" c="dimmed" ff="monospace" h={14}>
        {label}
      </Text>
      <svg width="44" height="12" viewBox="0 0 44 12" aria-hidden>
        <line x1={both ? 6 : 2} y1="6" x2="38" y2="6" stroke="var(--mantine-color-dimmed)" strokeWidth="1.5" />
        <path d="M36 2 L42 6 L36 10" fill="none" stroke="var(--mantine-color-dimmed)" strokeWidth="1.5" />
        {both && <path d="M8 2 L2 6 L8 10" fill="none" stroke="var(--mantine-color-dimmed)" strokeWidth="1.5" />}
      </svg>
    </Stack>
  );
}

type BufferCardProps = {
  catalog: Catalog;
  info: BufferInfo;
  config: BufferConfig;
  onChange: (config: BufferConfig) => void;
  disabled?: boolean;
};

function BufferCard({ catalog, info, config, onChange, disabled }: BufferCardProps) {
  const heuristicName = config.heuristic?.name ?? "fifo";
  const heuristic = findHeuristic(catalog, heuristicName);
  const params = heuristicParams(heuristic, config.heuristic?.params);
  const memory = bufferMemory(catalog, config.capacity, heuristicName, params);

  const setHeuristic = (name: string) => {
    const next = findHeuristic(catalog, name);
    onChange({ ...config, heuristic: { name, params: { ...(next?.default_params ?? {}) } } });
  };

  return (
    <Paper
      withBorder
      p="sm"
      w={420}
      radius="md"
      style={info.holds_model ? { borderColor: "var(--mantine-color-blue-5)", borderWidth: 2 } : undefined}
    >
      <Group justify="space-between" wrap="nowrap" gap="xs">
        <Tooltip label={info.description} multiline maw={320}>
          <Text fw={600} size="sm" truncate>
            {info.label}
          </Text>
        </Tooltip>
        <Group gap={4} wrap="nowrap">
          {info.holds_model && (
            <Badge size="xs" variant="light" color="blue">
              read by emit
            </Badge>
          )}
          <Badge size="xs" variant="default">
            {formatCount(memory)} entries
          </Badge>
        </Group>
      </Group>
      <Text size="xs" c="dimmed" ff="monospace" mb="xs" lineClamp={2}>
        {info.key} → {info.value}
      </Text>
      <Group gap="xs" align="flex-end" wrap="nowrap">
        <NumberInput
          size="xs"
          w={110}
          label="Capacity c"
          min={1}
          allowDecimal={false}
          value={config.capacity}
          disabled={disabled}
          onChange={(value) => onChange({ ...config, capacity: Math.max(1, Number(value) || 1) })}
        />
        <Select
          size="xs"
          flex={1}
          label="Heuristic H"
          value={heuristicName}
          disabled={disabled}
          allowDeselect={false}
          data={catalog.heuristics.map((h) => ({
            value: h.name,
            label: h.label,
            disabled: h.needs_lifecycle_values && !info.lifecycle_values,
          }))}
          onChange={(value) => value && setHeuristic(value)}
        />
      </Group>
      {heuristic && (
        <Box
          mt="xs"
          p="xs"
          style={{ border: "1px dashed var(--mantine-color-default-border)", borderRadius: "var(--mantine-radius-sm)" }}
        >
          <Text size="xs" c="dimmed" mb={4}>
            {heuristic.description}
          </Text>
          {!disabled && (
            <ParamsFields
              schema={heuristic.params_schema}
              values={params}
              onChange={(values) => onChange({ ...config, heuristic: { name: heuristicName, params: values } })}
            />
          )}
          {heuristic.private_buffers.length > 0 && (
            <Stack gap={2} mt={6}>
              {heuristic.private_buffers.map((privateBuffer) => {
                const capacity =
                  privateBuffer.capacity === "c" ? config.capacity : Number(params[privateBuffer.capacity] ?? 0);
                const nested = privateBuffer.heuristic ? findHeuristic(catalog, privateBuffer.heuristic) : undefined;
                return (
                  <Group key={privateBuffer.name} gap={6} wrap="nowrap">
                    <Badge size="xs" variant="outline" color="gray" style={{ flexShrink: 0 }}>
                      private
                    </Badge>
                    <Text size="xs" ff="monospace" style={{ flexShrink: 0 }}>
                      {privateBuffer.name}
                    </Text>
                    <Text size="xs" c="dimmed" truncate title={privateBuffer.description}>
                      {privateBuffer.capacity === "c" ? "c" : privateBuffer.capacity} = {formatCount(capacity)}
                      {nested ? ` · ${nested.label}` : ""} · {privateBuffer.description}
                    </Text>
                  </Group>
                );
              })}
            </Stack>
          )}
        </Box>
      )}
    </Paper>
  );
}
