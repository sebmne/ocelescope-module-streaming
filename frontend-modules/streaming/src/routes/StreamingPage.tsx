import {
  Alert,
  Badge,
  Box,
  Button,
  Center,
  Checkbox,
  Divider,
  Group,
  Loader,
  ScrollArea,
  SegmentedControl,
  Select,
  Stack,
  Switch,
  Tabs,
  Text,
  UnstyledButton,
} from "@mantine/core";
import { useCurrentOcel } from "@ocelescope/core";
import { useQueryClient } from "@tanstack/react-query";
import { PlayIcon } from "lucide-react";
import { useState } from "react";
import {
  type Catalog,
  getListReplaysQueryKey,
  type ReplaySummary,
  useGetCatalog,
  useListReplays,
  useStartReplay,
} from "../api/streaming";
import { ParamsFields } from "../components/ParamsFields";
import { ReplayView } from "../components/ReplayView";
import { TopologyEditor } from "../components/TopologyEditor";
import {
  type Draft,
  defaultDraft,
  draftMemory,
  findAlgorithm,
  formatCount,
  presetDraft,
  SPEEDS,
  toReplayConfig,
} from "../lib/config";

/**
 * Streaming discovery: choose a preset or an algorithm, edit the buffer topology (capacities and
 * heuristics), then watch a live replay of the current OCEL build the model.
 */
export default function StreamingPage() {
  const catalog = useGetCatalog();
  if (catalog.isError) {
    return (
      <Alert color="red" m="md" title="The streaming backend is not reachable">
        Is the backend module running?
      </Alert>
    );
  }
  if (!catalog.data) {
    return (
      <Center h="100%">
        <Loader />
      </Center>
    );
  }
  return <StreamingWorkspace catalog={catalog.data} />;
}

function initialDraft(catalog: Catalog): Draft {
  const preset = catalog.presets[0];
  return (preset && presetDraft(catalog, preset)) ?? defaultDraft(catalog.algorithms[0]!);
}

function StreamingWorkspace({ catalog }: { catalog: Catalog }) {
  const [draft, setDraft] = useState<Draft>(() => initialDraft(catalog));
  const [tab, setTab] = useState<string>("topology");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const replays = useListReplays({ query: { staleTime: 0, refetchInterval: 2000 } });
  const algorithm = findAlgorithm(catalog, draft.algorithm);

  const edit = (changes: Partial<Draft>) => setDraft((current) => ({ ...current, ...changes, presetKey: null }));

  return (
    <Group h="100%" gap={0} wrap="nowrap" align="stretch">
      <Box w={340} style={{ flexShrink: 0, borderRight: "1px solid var(--mantine-color-default-border)" }}>
        <ScrollArea h="100%">
          <Stack gap="sm" p="md">
            <Select
              label="Preset"
              placeholder="Custom configuration"
              value={draft.presetKey}
              data={catalog.presets.map((preset) => ({ value: preset.key, label: preset.label }))}
              onChange={(key) => {
                const preset = catalog.presets.find((p) => p.key === key);
                const next = preset && presetDraft(catalog, preset, draft);
                if (next) setDraft(next);
              }}
              description={catalog.presets.find((p) => p.key === draft.presetKey)?.description}
            />
            <Select
              label="Algorithm"
              allowDeselect={false}
              value={draft.algorithm}
              data={catalog.algorithms.map((a) => ({ value: a.key, label: a.label }))}
              onChange={(key) => {
                const next = key && findAlgorithm(catalog, key);
                if (next) setDraft(defaultDraft(next, draft));
              }}
              description={algorithm?.description}
            />
            {algorithm && (
              <ParamsFields
                size="sm"
                schema={algorithm.params_schema}
                values={draft.params}
                onChange={(params) => edit({ params })}
              />
            )}
            <Stack gap={4}>
              <Text size="sm" fw={500}>
                Stream items
              </Text>
              <Group gap="md">
                {(["events", "o2o_updates", "attribute_updates"] as const).map((kind) => (
                  <Checkbox
                    key={kind}
                    size="xs"
                    label={{ events: "Events", o2o_updates: "O2O", attribute_updates: "Attributes" }[kind]}
                    checked={Boolean(draft.stream[kind])}
                    onChange={(event) => edit({ stream: { ...draft.stream, [kind]: event.currentTarget.checked } })}
                  />
                ))}
              </Group>
            </Stack>
            <Stack gap={4}>
              <Text size="sm" fw={500}>
                Replay speed
              </Text>
              <SegmentedControl
                size="xs"
                data={SPEEDS}
                value={String(draft.speed)}
                onChange={(value) => setDraft({ ...draft, speed: Number(value) })}
              />
            </Stack>
            <Switch
              label="Track buffer fill"
              description="Plot the size of every buffer over the replay"
              checked={draft.trackBuffers}
              onChange={(event) => setDraft({ ...draft, trackBuffers: event.currentTarget.checked })}
            />
            <Text size="sm">
              Memory: <b>{formatCount(draftMemory(catalog, draft))}</b> entries
              <Text span size="xs" c="dimmed">
                {" "}
                (all capacities, including private buffers)
              </Text>
            </Text>
            <StartButton
              draft={draft}
              name={catalog.presets.find((p) => p.key === draft.presetKey)?.label}
              onStarted={(id) => {
                setSelectedId(id);
                setTab("replay");
              }}
            />
            <Divider label="Replays" labelPosition="left" />
            <ReplayList
              replays={replays.data ?? []}
              selectedId={selectedId}
              onSelect={(id) => {
                setSelectedId(id);
                setTab("replay");
              }}
            />
          </Stack>
        </ScrollArea>
      </Box>
      <Tabs value={tab} onChange={(value) => value && setTab(value)} flex={1} miw={0} display="flex" style={{ flexDirection: "column" }}>
        <Tabs.List>
          <Tabs.Tab value="topology">Buffer topology</Tabs.Tab>
          <Tabs.Tab value="replay">Live replay</Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="topology" flex={1} mih={0}>
          <ScrollArea h="100%">
            {algorithm && (
              <TopologyEditor
                catalog={catalog}
                algorithm={algorithm}
                buffers={draft.buffers}
                onChange={(name, config) => edit({ buffers: { ...draft.buffers, [name]: config } })}
              />
            )}
          </ScrollArea>
        </Tabs.Panel>
        <Tabs.Panel value="replay" flex={1} mih={0}>
          {selectedId ? (
            <ReplayView key={selectedId} catalog={catalog} replayId={selectedId} />
          ) : (
            <Center h="100%">
              <Text c="dimmed">Start a replay or select one on the left.</Text>
            </Center>
          )}
        </Tabs.Panel>
      </Tabs>
    </Group>
  );
}

function StartButton({ draft, name, onStarted }: { draft: Draft; name?: string; onStarted: (id: string) => void }) {
  const { id: ocelId } = useCurrentOcel();
  const queryClient = useQueryClient();
  const start = useStartReplay({
    mutation: {
      onSuccess: (replay) => {
        queryClient.invalidateQueries({ queryKey: getListReplaysQueryKey() });
        onStarted(replay.id);
      },
    },
  });
  const error = start.error as { response?: { data?: { detail?: unknown } } } | null;
  return (
    <Stack gap={4}>
      <Button
        leftSection={<PlayIcon size={16} />}
        disabled={!ocelId}
        loading={start.isPending}
        onClick={() => ocelId && start.mutate({ data: toReplayConfig(draft, ocelId, name) })}
      >
        Start replay
      </Button>
      {error && (
        <Text size="xs" c="red">
          {String(error.response?.data?.detail ?? "Could not start the replay")}
        </Text>
      )}
    </Stack>
  );
}

const STATE_COLORS: Record<string, string> = {
  starting: "gray",
  running: "blue",
  paused: "yellow",
  finished: "green",
  cancelled: "gray",
  failed: "red",
};

function ReplayList({
  replays,
  selectedId,
  onSelect,
}: {
  replays: ReplaySummary[];
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  if (replays.length === 0) {
    return (
      <Text size="xs" c="dimmed">
        No replays yet.
      </Text>
    );
  }
  return (
    <Stack gap={4}>
      {replays.map((replay) => (
        <UnstyledButton
          key={replay.id}
          onClick={() => onSelect(replay.id)}
          p={6}
          style={{
            borderRadius: "var(--mantine-radius-sm)",
            background: replay.id === selectedId ? "var(--mantine-color-default-hover)" : undefined,
          }}
        >
          <Group justify="space-between" wrap="nowrap" gap="xs">
            <Text size="xs" truncate>
              {replay.name}
            </Text>
            <Badge size="xs" variant="light" color={STATE_COLORS[replay.state]} style={{ flexShrink: 0 }}>
              {replay.state === "running" && replay.total
                ? `${Math.floor((100 * replay.position) / replay.total)}%`
                : replay.state}
            </Badge>
          </Group>
        </UnstyledButton>
      ))}
    </Stack>
  );
}
