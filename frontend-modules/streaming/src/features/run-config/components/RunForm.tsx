import { Alert, Button, Divider, List, ScrollArea, Stack, TextInput } from "@mantine/core";
import { useQueryClient } from "@tanstack/react-query";
import { PlayIcon } from "lucide-react";
import { type Catalog, getListRunsQueryKey, type RunSummary, useStartRun } from "../../../api/streaming";
import { useRunForm } from "../hooks/useRunForm";
import { toRunConfig } from "../model";
import { AlgorithmSection } from "./AlgorithmSection";
import { BufferList } from "./BufferList";
import { StreamSection } from "./StreamSection";

type RunFormProps = {
  catalog: Catalog;
  ocelId: string;
  onStarted: (run: RunSummary) => void;
};

/** The run configuration: a scrollable form with the start button pinned to the bottom. */
export function RunForm({ catalog, ocelId, onStarted }: RunFormProps) {
  const { state, dispatch, algorithm, errors } = useRunForm(catalog);
  const queryClient = useQueryClient();
  const startRun = useStartRun({
    mutation: {
      onSuccess: async (run) => {
        await queryClient.invalidateQueries({ queryKey: getListRunsQueryKey() });
        onStarted(run);
      },
    },
  });

  if (!algorithm) return null;

  return (
    <Stack gap={0} h="100%">
      <ScrollArea flex={1} mih={0} offsetScrollbars>
        <Stack gap="md" px="md" py="xs">
          <AlgorithmSection
            algorithms={catalog.algorithms}
            selected={algorithm}
            params={state.algorithmParams}
            onSelect={(selected) => dispatch({ type: "selectAlgorithm", algorithm: selected })}
            onParamsChange={(params) => dispatch({ type: "setAlgorithmParams", params })}
          />
          <StreamSection stream={state.stream} onChange={(stream) => dispatch({ type: "setStream", stream })} />
          <BufferList
            buffers={algorithm.buffers}
            heuristics={catalog.heuristics}
            values={state.buffers}
            onChange={(buffer, patch) => dispatch({ type: "updateBuffer", buffer, patch })}
          />
          <TextInput
            label="Run name"
            placeholder="Derived from the configuration"
            value={state.name}
            onChange={(event) => dispatch({ type: "setName", name: event.currentTarget.value })}
          />
        </Stack>
      </ScrollArea>
      <Divider />
      <Stack gap="xs" p="md">
        {errors.length > 0 && (
          <Alert color="yellow" p="xs">
            <List size="xs">
              {errors.map((error) => (
                <List.Item key={error}>{error}</List.Item>
              ))}
            </List>
          </Alert>
        )}
        {startRun.error && (
          <Alert color="red" p="xs" title="The run could not be started">
            {errorMessage(startRun.error)}
          </Alert>
        )}
        <Button
          fullWidth
          leftSection={<PlayIcon size={16} />}
          disabled={errors.length > 0}
          loading={startRun.isPending}
          onClick={() => startRun.mutate({ data: toRunConfig(state, ocelId) })}
        >
          Start run
        </Button>
      </Stack>
    </Stack>
  );
}

function errorMessage(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
  if (typeof detail === "string") return detail;
  return error instanceof Error ? error.message : "Unknown error";
}
