import {
  Accordion,
  Badge,
  Button,
  Group,
  NumberInput,
  Paper,
  SegmentedControl,
  Select,
  Stack,
  Text,
  Tooltip,
} from "@mantine/core";
import { useElementSize } from "@mantine/hooks";
import { InfoIcon } from "lucide-react";
import { useState } from "react";
import type { BufferInfo, HeuristicInfo } from "../../../api/streaming";
import { LabelWithInfo } from "../../../components/LabelWithInfo";
import { SchemaForm } from "../../../components/SchemaForm";
import {
  BUFFER_MODES,
  type BufferFormState,
  type BufferMode,
  DEFAULT_CAPACITY,
  hasCapacity,
  heuristicsFor,
} from "../model";

type BufferListProps = {
  buffers: BufferInfo[];
  heuristics: HeuristicInfo[];
  values: Record<string, BufferFormState>;
  onChange: (buffer: string, patch: Partial<BufferFormState>) => void;
  onChangeMany: (buffers: string[], patch: Partial<BufferFormState>) => void;
};

/**
 * Eviction settings per buffer. Buffers that grow with the stream come first, with a quick setup
 * that configures all of them at once; buffers bounded by the log's vocabulary are collapsed.
 */
export function BufferList({ buffers, heuristics, values, onChange, onChangeMany }: BufferListProps) {
  const growing = buffers.filter((buffer) => !buffer.bounded_by);
  const bounded = buffers.filter((buffer) => buffer.bounded_by);

  const card = (buffer: BufferInfo) => (
    <BufferCard
      key={buffer.name}
      buffer={buffer}
      heuristics={heuristics}
      value={values[buffer.name]}
      onChange={(patch) => onChange(buffer.name, patch)}
    />
  );

  return (
    <Stack gap="xs">
      <div>
        <Text size="sm" fw={500}>
          Buffers
        </Text>
        <Text size="xs" c="dimmed">
          Everything the algorithm remembers is stored in buffers. Bound the buffers that grow with the stream to limit
          memory; a heuristic then decides which entries are forgotten.
        </Text>
      </div>
      {growing.length > 0 && (
        <QuickSetup
          heuristics={heuristics}
          count={growing.length}
          onApply={(patch) =>
            onChangeMany(
              growing.map((buffer) => buffer.name),
              patch,
            )
          }
        />
      )}
      {growing.map(card)}
      {bounded.length > 0 && (
        <Accordion variant="contained" radius="sm" chevronPosition="left">
          <Accordion.Item value="bounded">
            <Accordion.Control>
              <Text size="sm">Bounded by the log's vocabulary ({bounded.length})</Text>
              <Text size="xs" c="dimmed">
                At most one entry per activity or activity–type combination: finite for every log, so usually left
                unbounded.
              </Text>
            </Accordion.Control>
            <Accordion.Panel>
              <Stack gap="xs">{bounded.map(card)}</Stack>
            </Accordion.Panel>
          </Accordion.Item>
        </Accordion>
      )}
    </Stack>
  );
}

type ModeSwitchProps = {
  heuristics: HeuristicInfo[];
  value: BufferMode;
  onChange: (mode: BufferMode) => void;
};

/** Switches between the eviction modes that at least one heuristic supports. */
function ModeSwitch({ heuristics, value, onChange }: ModeSwitchProps) {
  const modes = BUFFER_MODES.filter((mode) => mode.value === "unbounded" || heuristicsFor(heuristics, mode.value).length);
  // Side by side if the labels fit, stacked in a narrow panel.
  const { ref, width } = useElementSize();
  const vertical = width > 0 && width < modes.length * 72;
  return (
    <div ref={ref}>
      <SegmentedControl
        fullWidth
        size="xs"
        orientation={vertical ? "vertical" : "horizontal"}
        value={value}
        onChange={(mode) => onChange(mode as BufferMode)}
        data={modes.map((mode) => ({
          value: mode.value,
          label: (
            <Tooltip label={mode.description} multiline w={240} openDelay={300}>
              <span>{mode.label}</span>
            </Tooltip>
          ),
        }))}
      />
    </div>
  );
}

type QuickSetupProps = {
  heuristics: HeuristicInfo[];
  count: number;
  onApply: (patch: Partial<BufferFormState>) => void;
};

/** Configures all buffers that grow with the stream at once. */
function QuickSetup({ heuristics, count, onApply }: QuickSetupProps) {
  const [mode, setMode] = useState<BufferMode>("capacity");
  const [capacity, setCapacity] = useState(DEFAULT_CAPACITY);
  const candidates = heuristicsFor(heuristics, mode);
  const [heuristic, setHeuristic] = useState<string | null>(candidates[0]?.key ?? null);
  const selected = candidates.find((candidate) => candidate.key === heuristic) ?? candidates[0];

  return (
    <Paper withBorder p="sm" radius="sm" bg="var(--mantine-color-default-hover)">
      <Stack gap="xs">
        <div>
          <Text size="sm" fw={500}>
            Quick setup
          </Text>
          <Text size="xs" c="dimmed">
            Sets all {count} buffers that grow with the stream at once; adjust single buffers below.
          </Text>
        </div>
        <ModeSwitch heuristics={heuristics} value={mode} onChange={setMode} />
        {mode !== "unbounded" && (
          <Group grow gap="xs" align="flex-start">
            {hasCapacity(mode) && (
              <NumberInput
                label="Capacity"
                size="xs"
                value={capacity}
                min={0}
                step={100}
                allowDecimal={false}
                thousandSeparator=" "
                onChange={(value) => typeof value === "number" && setCapacity(value)}
              />
            )}
            <Select
              label={selected ? <LabelWithInfo label="Heuristic" info={selected.description} /> : "Heuristic"}
              size="xs"
              data={candidates.map((candidate) => ({ value: candidate.key, label: candidate.label }))}
              value={selected?.key ?? null}
              allowDeselect={false}
              onChange={setHeuristic}
            />
          </Group>
        )}
        <Button
          size="xs"
          variant="light"
          onClick={() =>
            onApply(
              mode === "unbounded"
                ? { mode }
                : { mode, capacity, heuristic: selected?.key ?? null, heuristicParams: {} },
            )
          }
        >
          Apply to {count === 1 ? "the growing buffer" : `all ${count}`}
        </Button>
      </Stack>
    </Paper>
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

  const setMode = (mode: BufferMode) => {
    const keep = heuristicsFor(heuristics, mode).some((candidate) => candidate.key === value.heuristic);
    const first = heuristicsFor(heuristics, mode)[0]?.key ?? null;
    onChange(keep ? { mode } : { mode, heuristic: first, heuristicParams: {} });
  };

  return (
    <Paper withBorder p="sm" radius="sm">
      <Stack gap="xs">
        <Group gap={6} wrap="nowrap" justify="space-between">
          <Group gap={6} wrap="nowrap">
            <Text size="sm" fw={500}>
              {buffer.label}
            </Text>
            <Tooltip
              multiline
              w={280}
              withArrow
              label={
                <Stack gap={4}>
                  <Text size="xs">{buffer.description}</Text>
                  {buffer.bounded_by && <Text size="xs">{buffer.bounded_by}</Text>}
                </Stack>
              }
            >
              <InfoIcon size={14} color="var(--mantine-color-dimmed)" style={{ flexShrink: 0 }} />
            </Tooltip>
          </Group>
          {value.mode !== "unbounded" && (
            <Badge size="xs" variant="light">
              {heuristic?.label ?? "no heuristic"}
              {hasCapacity(value.mode) ? ` · ${value.capacity}` : ""}
            </Badge>
          )}
        </Group>
        <ModeSwitch heuristics={heuristics} value={value.mode} onChange={setMode} />
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
                label={heuristic ? <LabelWithInfo label="Heuristic" info={heuristic.description} /> : "Heuristic"}
                size="xs"
                data={candidates.map((candidate) => ({ value: candidate.key, label: candidate.label }))}
                value={heuristic ? heuristic.key : null}
                allowDeselect={false}
                onChange={(key) => onChange({ heuristic: key, heuristicParams: {} })}
              />
            </Group>
            {heuristic && (
              <SchemaForm
                schema={heuristic.params_schema}
                value={value.heuristicParams}
                onChange={(heuristicParams) => onChange({ heuristicParams })}
              />
            )}
          </>
        )}
      </Stack>
    </Paper>
  );
}
