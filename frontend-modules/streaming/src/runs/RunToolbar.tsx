import { ActionIcon, Button, Group, Progress, Select, Text, Tooltip } from "@mantine/core";
import { PlayIcon, SettingsIcon, SquareIcon } from "lucide-react";
import type { AlgorithmInfo, RunSummary } from "../api/streaming";
import { properties } from "../settings/schema";
import { isActive } from "./useRuns";

const count = new Intl.NumberFormat();

type Props = {
  algorithms: AlgorithmInfo[];
  algorithm: AlgorithmInfo | undefined;
  onAlgorithm: (key: string) => void;
  onSettings: () => void;
  run: RunSummary | undefined;
  onStart: () => void;
  onCancel: () => void;
  controls: React.ReactNode;
  children: React.ReactNode;
};

/** What to run and how far the shown run is; `controls` follow the run button, `children` go to the right end. */
export function RunToolbar(props: Props) {
  const { algorithms, algorithm, onAlgorithm, onSettings, run, onStart, onCancel, controls, children } = props;
  const active = run !== undefined && isActive(run);
  return (
    <Group px="md" py="xs" gap="sm" wrap="nowrap" style={{ borderBottom: "1px solid var(--mantine-color-default-border)" }}>
      <Select
        aria-label="Algorithm"
        data={algorithms.map(({ key, label }) => ({ value: key, label }))}
        value={algorithm?.key ?? null}
        onChange={(key) => key && onAlgorithm(key)}
        allowDeselect={false}
        w={260}
      />
      {algorithm && properties(algorithm.config_schema).length > 0 && (
        <Tooltip label="Settings">
          <ActionIcon variant="default" size="input-sm" aria-label="Settings" onClick={onSettings}>
            <SettingsIcon size={18} />
          </ActionIcon>
        </Tooltip>
      )}
      {active ? (
        <Button color="red" variant="light" leftSection={<SquareIcon size={14} />} onClick={onCancel}>
          Cancel
        </Button>
      ) : (
        <Button leftSection={<PlayIcon size={14} />} disabled={!algorithm} onClick={onStart}>
          Run
        </Button>
      )}
      {controls}
      <Group gap="sm" wrap="nowrap" flex={1} miw={0}>
        {run && (
          <>
            <Progress value={run.total ? (100 * run.processed) / run.total : 0} animated={active} w={200} />
            <Text size="sm" c="dimmed" truncate>
              {run.phase === "layout" && "Preparing layout · "}
              {count.format(run.processed)} / {run.total === null ? "…" : count.format(run.total)} items
              {run.duration !== null && ` · ${run.duration.toFixed(2)} s`}
            </Text>
          </>
        )}
      </Group>
      {children}
    </Group>
  );
}
