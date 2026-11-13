import { Alert, Center, Group, Progress, Splitter, Stack, Text } from "@mantine/core";
import { ResourceViewer } from "@ocelescope/resources";
import type { RunSummary } from "../api/streaming";
import type { View } from "./RunBar";
import { isActive } from "./useRuns";

const format = new Intl.NumberFormat();
const percent = new Intl.NumberFormat(undefined, { style: "percent", maximumFractionDigits: 1 });

/** The selected run: its progress or outcome, then key figures and the models. */
export function RunView({ run, view }: { run: RunSummary | undefined; view: View }) {
  if (!run) return <Message>Configure a run in the panel on the right and start it.</Message>;
  if (isActive(run.state)) {
    return (
      <Center h="100%">
        <Stack w={320} gap="xs">
          <Text size="sm" ta="center">
            {format.format(run.processed)} of {format.format(run.total ?? 0)} items
          </Text>
          <Progress animated value={run.total ? (100 * run.processed) / run.total : 0} />
        </Stack>
      </Center>
    );
  }
  if (run.error) {
    return (
      <Center h="100%" p="md">
        <Alert color="red" title="The run failed" maw={560}>
          {run.error}
        </Alert>
      </Center>
    );
  }
  if (!run.model_id || !run.reference_id) return <Message>The run was cancelled.</Message>;

  return (
    <Stack gap={0} h="100%">
      <Group px="sm" py={6} gap="lg" style={{ borderBottom: "1px solid var(--mantine-color-default-border)" }}>
        {Object.entries(run.scores ?? {}).map(([element, f1]) => (
          <Figure key={element} label={`${element} F1`} value={percent.format(f1)} />
        ))}
        {run.buffers
          .filter((buffer) => buffer.capacity !== null)
          .map((buffer) => (
            <Figure
              key={buffer.name}
              label={`${buffer.name}: evicted / too early`}
              value={`${format.format(buffer.evictions)} / ${format.format(buffer.premature)}`}
            />
          ))}
        <Figure label="time" value={`${(run.duration ?? 0).toFixed(2)} s`} />
      </Group>
      <div style={{ flex: 1, minHeight: 0 }}>
        {view === "both" ? (
          <Splitter h="100%" lineSize={4} handleColor="var(--mantine-color-default-border)">
            <Splitter.Pane defaultSize={50}>
              <ResourceViewer id={run.model_id} />
            </Splitter.Pane>
            <Splitter.Pane defaultSize={50}>
              <ResourceViewer id={run.reference_id} />
            </Splitter.Pane>
          </Splitter>
        ) : (
          <ResourceViewer key={view} id={view === "model" ? run.model_id : run.reference_id} />
        )}
      </div>
    </Stack>
  );
}

function Figure({ label, value }: { label: string; value: string }) {
  return (
    <Group gap={4} wrap="nowrap">
      <Text size="xs" c="dimmed" tt="capitalize">
        {label}
      </Text>
      <Text size="sm" fw={600}>
        {value}
      </Text>
    </Group>
  );
}

function Message({ children }: { children: string }) {
  return (
    <Center h="100%" p="md">
      <Text c="dimmed">{children}</Text>
    </Center>
  );
}
