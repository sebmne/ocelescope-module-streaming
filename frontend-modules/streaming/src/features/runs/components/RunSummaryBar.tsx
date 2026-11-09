import { Button, Divider, Group, Text, Tooltip } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { TableIcon } from "lucide-react";
import type { RunResult, RunSummary } from "../../../api/streaming";
import { useBufferLabel } from "../hooks/useBufferLabel";
import { formatInteger, formatPercent, formatSeconds } from "../lib/format";
import { RunDetailsModal } from "./RunDetailsModal";

type RunSummaryBarProps = {
  run: RunSummary;
  result: RunResult;
};

/** Key figures of a finished run in one line; the full tables open in a modal. */
export function RunSummaryBar({ run, result }: RunSummaryBarProps) {
  const [detailsOpen, details] = useDisclosure(false);
  const bufferLabel = useBufferLabel(run.config.algorithm);
  const boundedBuffers = Object.entries(result.buffers).filter(([, stats]) => stats.capacity !== null);

  return (
    <Group
      px="sm"
      py={6}
      gap="md"
      wrap="wrap"
      style={{ borderBottom: "1px solid var(--mantine-color-default-border)" }}
    >
      {Object.entries(result.scores).map(([element, score]) => (
        <Tooltip
          key={element}
          label={`Precision ${formatPercent(score.precision)} · Recall ${formatPercent(score.recall)}`}
        >
          <Group gap={4} wrap="nowrap">
            <Text size="xs" c="dimmed" tt="capitalize">
              {element} F1
            </Text>
            <Text size="sm" fw={600}>
              {formatPercent(score.f1)}
            </Text>
          </Group>
        </Tooltip>
      ))}
      {boundedBuffers.length > 0 && <Divider orientation="vertical" />}
      {boundedBuffers.map(([buffer, stats]) => (
        <Group key={buffer} gap={4} wrap="nowrap">
          <Text size="xs" c="dimmed">
            {bufferLabel(buffer)} evicted
          </Text>
          <Text size="sm" fw={600}>
            {formatInteger(stats.evictions)}
          </Text>
          <Text size="xs" c="dimmed">
            · too early
          </Text>
          <Text size="sm" fw={600}>
            {formatInteger(stats.premature_evictions)}
          </Text>
        </Group>
      ))}
      <Text size="xs" c="dimmed">
        {formatSeconds(result.duration_seconds)}
      </Text>
      <Button size="compact-xs" variant="subtle" leftSection={<TableIcon size={14} />} onClick={details.open} ml="auto">
        Details
      </Button>
      <RunDetailsModal
        title={run.name}
        result={result}
        bufferLabel={bufferLabel}
        opened={detailsOpen}
        onClose={details.close}
      />
    </Group>
  );
}
