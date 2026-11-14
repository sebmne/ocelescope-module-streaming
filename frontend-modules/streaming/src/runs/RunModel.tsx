import { Alert, Center, Stack, Text } from "@mantine/core";
import { ResourceViewer } from "@ocelescope/resources";
import type { RunSummary } from "../api/streaming";

/** The run's final model, or its latest snapshot while running or after a cancel. */
export function RunModel({ run }: { run: RunSummary | undefined }) {
  if (!run) return <Hint>Choose an algorithm and start a run. Its model appears here as it grows.</Hint>;
  if (run.error) {
    return (
      <Center h="100%" p="md">
        <Alert color="red" title="The run failed" maw={560}>
          {run.error}
        </Alert>
      </Center>
    );
  }
  const id = run.result_id ?? run.snapshot_id;
  if (!id) return <Hint>{run.state === "CANCELLED" ? "Cancelled before the first snapshot." : "Waiting for the first snapshot…"}</Hint>;
  return (
    <Stack h="100%" gap={0}>
      {run.state === "CANCELLED" && (
        <Text size="xs" c="dimmed" px="md" py={4}>
          Cancelled: showing the last snapshot.
        </Text>
      )}
      <div style={{ flex: 1, minHeight: 0 }}>
        <ResourceViewer id={id} />
      </div>
    </Stack>
  );
}

function Hint({ children }: { children: string }) {
  return (
    <Center h="100%" p="md">
      <Text c="dimmed">{children}</Text>
    </Center>
  );
}
