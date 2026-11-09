import { Alert, Center, LoadingOverlay, Progress, Stack, Text } from "@mantine/core";
import type { RunSummary } from "../../../api/streaming";
import { formatInteger } from "../lib/format";
import type { ModelView } from "../lib/modelView";
import { progressPercent } from "../lib/progress";
import { isActive } from "../lib/runState";
import { ModelCanvas } from "./ModelCanvas";

type RunCanvasProps = {
  run: RunSummary | undefined;
  view: ModelView;
  isLoading: boolean;
};

/** The main area: the selected run's models, or its progress or outcome while there are none. */
export function RunCanvas({ run, view, isLoading }: RunCanvasProps) {
  if (isLoading) return <LoadingOverlay visible />;
  if (!run) return <Message>Configure a run in the panel on the right and start it.</Message>;
  if (run.result) return <ModelCanvas result={run.result} view={view} />;

  if (isActive(run.state)) {
    const { processed = 0, total } = run.progress;
    return (
      <Center h="100%">
        <Stack gap="xs" w={320} align="stretch">
          <Text size="sm" ta="center">
            Processing {formatInteger(processed)}
            {total ? ` of ${formatInteger(total)}` : ""} items
          </Text>
          <Progress value={progressPercent(run)} animated />
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
  return <Message>The run was cancelled.</Message>;
}

function Message({ children }: { children: React.ReactNode }) {
  return (
    <Center h="100%" p="md">
      <Text c="dimmed">{children}</Text>
    </Center>
  );
}
