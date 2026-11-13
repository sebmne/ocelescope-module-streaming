import { Alert, Button, Chip, Group, ScrollArea, Select, Stack, Text, TextInput } from "@mantine/core";
import { useQueryClient } from "@tanstack/react-query";
import { PlayIcon } from "lucide-react";
import { type Catalog, getListRunsQueryKey, type RunSummary, useStartRun } from "../api/streaming";
import { BufferField } from "./BufferField";
import { type Kind, toRunConfig, useConfig } from "./useConfig";

const KIND_LABELS: Record<Kind, string> = {
  events: "Events",
  o2o_updates: "O2O updates",
  attribute_updates: "Attribute updates",
};

type ConfigPanelProps = { catalog: Catalog; ocelId: string; onStarted: (run: RunSummary) => void };

/** Configures and starts a run. */
export function ConfigPanel({ catalog, ocelId, onStarted }: ConfigPanelProps) {
  const { config, selectAlgorithm, setKinds, setBuffer, setName } = useConfig(catalog.algorithms, catalog.heuristics[0].key);
  const queryClient = useQueryClient();
  const start = useStartRun({
    mutation: {
      onSuccess: async (run) => {
        await queryClient.invalidateQueries({ queryKey: getListRunsQueryKey() });
        onStarted(run);
      },
    },
  });

  return (
    <Stack gap={0} h="100%">
      <ScrollArea flex={1} mih={0} offsetScrollbars>
        <Stack gap="md" p="md">
          <Select
            label="Algorithm"
            allowDeselect={false}
            data={catalog.algorithms.map(({ key, label }) => ({ value: key, label }))}
            value={config.algorithm.key}
            onChange={(key) => key && selectAlgorithm(key)}
          />
          <Stack gap={6}>
            <Text size="sm" fw={500}>
              Stream items
            </Text>
            <Chip.Group multiple value={config.kinds} onChange={(kinds) => setKinds(kinds as Kind[])}>
              <Group gap={6}>
                {Object.entries(KIND_LABELS).map(([kind, label]) => (
                  <Chip key={kind} value={kind} size="xs">
                    {label}
                  </Chip>
                ))}
              </Group>
            </Chip.Group>
          </Stack>
          <Stack gap="xs">
            <Text size="sm" fw={500}>
              Buffers
            </Text>
            {config.algorithm.buffers.map((name) => (
              <BufferField
                key={name}
                name={name}
                value={config.buffers[name]}
                heuristics={catalog.heuristics}
                onChange={(patch) => setBuffer(name, patch)}
              />
            ))}
          </Stack>
          <TextInput
            label="Run name"
            placeholder="Derived from the configuration"
            value={config.name}
            onChange={(event) => setName(event.currentTarget.value)}
          />
        </Stack>
      </ScrollArea>
      <Stack gap="xs" p="md" style={{ borderTop: "1px solid var(--mantine-color-default-border)" }}>
        {start.error && (
          <Alert color="red" p="xs">
            {errorMessage(start.error)}
          </Alert>
        )}
        <Button
          fullWidth
          leftSection={<PlayIcon size={16} />}
          disabled={config.kinds.length === 0}
          loading={start.isPending}
          onClick={() => start.mutate({ data: toRunConfig(config, ocelId) })}
        >
          Start run
        </Button>
      </Stack>
    </Stack>
  );
}

function errorMessage(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
  return typeof detail === "string" ? detail : "The run could not be started.";
}
