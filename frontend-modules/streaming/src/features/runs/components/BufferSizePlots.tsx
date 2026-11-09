import { Box, Group, Paper, ScrollArea, Text, Tooltip } from "@mantine/core";
import type { BufferSizeSeries } from "../../../api/streaming";
import { formatInteger } from "../lib/format";

type BufferSizePlotsProps = {
  series: BufferSizeSeries;
  bufferLabel: (name: string) => string;
};

/** One small line plot of the number of entries per buffer over the stream. */
export function BufferSizePlots({ series, bufferLabel }: BufferSizePlotsProps) {
  return (
    <ScrollArea type="auto" offsetScrollbars style={{ borderBottom: "1px solid var(--mantine-color-default-border)" }}>
      <Group gap="xs" px="sm" py={6} wrap="nowrap">
        {Object.entries(series.sizes).map(([name, sizes]) => (
          <BufferSizePlot
            key={name}
            label={bufferLabel(name)}
            positions={series.positions}
            sizes={sizes}
            capacity={series.capacities[name] ?? null}
          />
        ))}
      </Group>
    </ScrollArea>
  );
}

const WIDTH = 200;
const HEIGHT = 56;
const PAD = 2;

type BufferSizePlotProps = {
  label: string;
  positions: number[];
  sizes: number[];
  capacity: number | null;
};

function BufferSizePlot({ label, positions, sizes, capacity }: BufferSizePlotProps) {
  const peak = Math.max(0, ...sizes);
  const top = Math.max(1, peak, capacity ?? 0) * 1.05;
  const first = positions[0] ?? 0;
  const span = Math.max(1, (positions[positions.length - 1] ?? 1) - first);
  const x = (position: number) => PAD + ((position - first) / span) * (WIDTH - 2 * PAD);
  const y = (size: number) => HEIGHT - PAD - (size / top) * (HEIGHT - 2 * PAD);
  const points = positions.map((position, i) => `${x(position)},${y(sizes[i] ?? 0)}`).join(" ");
  const last = sizes[sizes.length - 1] ?? 0;

  return (
    <Paper withBorder radius="sm" px={8} py={4} miw={WIDTH + 18}>
      <Group justify="space-between" gap={4} wrap="nowrap">
        <Text size="xs" fw={500} truncate maw={120}>
          {label}
        </Text>
        <Tooltip label={`Peak ${formatInteger(peak)} · final ${formatInteger(last)} · ${positions.length} samples`}>
          <Text size="xs" c="dimmed">
            {formatInteger(peak)}
            {capacity !== null && ` / ${formatInteger(capacity)}`}
          </Text>
        </Tooltip>
      </Group>
      <Box
        component="svg"
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        w={WIDTH}
        h={HEIGHT}
        display="block"
        aria-label={`Entries of ${label} over the stream`}
      >
        <line
          x1={PAD}
          x2={WIDTH - PAD}
          y1={HEIGHT - PAD}
          y2={HEIGHT - PAD}
          stroke="var(--mantine-color-default-border)"
          strokeWidth={1}
        />
        <polyline
          points={points}
          fill="none"
          stroke="var(--mantine-color-blue-6)"
          strokeWidth={1.5}
          strokeLinejoin="round"
        />
        {/* The limit is drawn last, so it stays visible while the buffer is full. */}
        {capacity !== null && (
          <line
            x1={PAD}
            x2={WIDTH - PAD}
            y1={y(capacity)}
            y2={y(capacity)}
            stroke="var(--mantine-color-gray-5)"
            strokeWidth={1}
            strokeDasharray="4 3"
          />
        )}
      </Box>
    </Paper>
  );
}
