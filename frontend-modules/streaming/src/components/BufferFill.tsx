import { Box, Group, Paper, ScrollArea, Text, Tooltip } from "@mantine/core";
import type { BufferStatus, FillSamples } from "../api/streaming";
import { formatCount } from "../lib/config";

const WIDTH = 180;
const HEIGHT = 44;
const PAD = 2;

type BufferFillProps = {
  buffers: BufferStatus[];
  fill: FillSamples | null;
  label: (path: string) => string;
};

/** One small card per buffer (and private buffer): its fill over the replay and its evictions. */
export function BufferFill({ buffers, fill, label }: BufferFillProps) {
  return (
    <ScrollArea type="auto" offsetScrollbars>
      <Group gap="xs" wrap="nowrap" px="sm" py={6}>
        {buffers.map((buffer) => (
          <BufferCard
            key={buffer.path}
            buffer={buffer}
            label={label(buffer.path)}
            positions={fill?.positions}
            sizes={fill?.sizes[buffer.path]}
          />
        ))}
      </Group>
    </ScrollArea>
  );
}

type BufferCardProps = {
  buffer: BufferStatus;
  label: string;
  positions?: number[];
  sizes?: number[];
};

function BufferCard({ buffer, label, positions, sizes }: BufferCardProps) {
  const isPrivate = buffer.path.includes("/");
  const premature = buffer.evictions ? buffer.premature / buffer.evictions : null;
  return (
    <Paper
      withBorder
      radius="sm"
      px={8}
      py={4}
      miw={WIDTH + 18}
      style={isPrivate ? { borderStyle: "dashed" } : undefined}
    >
      <Group justify="space-between" gap={4} wrap="nowrap">
        <Text size="xs" fw={500} truncate maw={110} title={buffer.path}>
          {label}
        </Text>
        <Text size="xs" c="dimmed">
          {formatCount(buffer.size)}
          {buffer.capacity !== null && ` / ${formatCount(buffer.capacity)}`}
        </Text>
      </Group>
      {positions && sizes ? (
        <Sparkline positions={positions} sizes={sizes} capacity={buffer.capacity} />
      ) : (
        <Box h={HEIGHT} />
      )}
      <Tooltip
        label="Evictions; premature evictions are those whose key was inserted again later (found so far)."
        multiline
        maw={260}
      >
        <Text size="10px" c="dimmed">
          {buffer.heuristic} · {formatCount(buffer.evictions)} evicted
          {buffer.deletions > 0 && ` · ${formatCount(buffer.deletions)} deleted`}
          {premature !== null && ` · ${(premature * 100).toFixed(1)}% premature`}
        </Text>
      </Tooltip>
    </Paper>
  );
}

function Sparkline({ positions, sizes, capacity }: { positions: number[]; sizes: number[]; capacity: number | null }) {
  const peak = Math.max(1, ...sizes, capacity ?? 0) * 1.05;
  const first = positions[0] ?? 0;
  const span = Math.max(1, (positions[positions.length - 1] ?? 1) - first);
  const x = (position: number) => PAD + ((position - first) / span) * (WIDTH - 2 * PAD);
  const y = (size: number) => HEIGHT - PAD - (size / peak) * (HEIGHT - 2 * PAD);
  const points = positions.map((position, i) => `${x(position)},${y(sizes[i] ?? 0)}`).join(" ");
  return (
    <Box component="svg" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} w={WIDTH} h={HEIGHT} display="block" aria-hidden>
      <line x1={PAD} x2={WIDTH - PAD} y1={HEIGHT - PAD} y2={HEIGHT - PAD} stroke="var(--mantine-color-default-border)" />
      <polyline points={points} fill="none" stroke="var(--mantine-color-blue-6)" strokeWidth={1.5} strokeLinejoin="round" />
      {capacity !== null && (
        <line
          x1={PAD}
          x2={WIDTH - PAD}
          y1={y(capacity)}
          y2={y(capacity)}
          stroke="var(--mantine-color-gray-5)"
          strokeDasharray="4 3"
        />
      )}
    </Box>
  );
}
