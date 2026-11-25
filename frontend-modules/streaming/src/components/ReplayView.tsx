import {
  ActionIcon,
  Alert,
  Badge,
  Box,
  Center,
  Group,
  Loader,
  Progress,
  SegmentedControl,
  Stack,
  Text,
  Tooltip,
} from "@mantine/core";
import { Visualization, type VisualizationsType } from "@ocelescope/resources";
import { useQueryClient } from "@tanstack/react-query";
import { PauseIcon, PlayIcon, SaveIcon, SquareIcon } from "lucide-react";
import { useEffect } from "react";
import {
  getGetReplayModelQueryKey,
  getGetReplayQueryKey,
  type Catalog,
  type ReplayStatus,
  useControlReplay,
  useGetReplay,
  useGetReplayModel,
  useSaveReplayModel,
} from "../api/streaming";
import { findAlgorithm, formatCount, SPEEDS } from "../lib/config";
import { BufferFill } from "./BufferFill";

const ACTIVE = new Set(["starting", "running", "paused"]);

const STATE_COLORS: Record<string, string> = {
  starting: "gray",
  running: "blue",
  paused: "yellow",
  finished: "green",
  cancelled: "gray",
  failed: "red",
};

/** A live replay: controls, progress, the fill of every buffer and the current model. */
export function ReplayView({ catalog, replayId }: { catalog: Catalog; replayId: string }) {
  const queryClient = useQueryClient();
  const status = useGetReplay(replayId, {
    query: { staleTime: 0, refetchInterval: (query) => (isActive(query.state.data) ? 500 : false) },
  });
  const active = isActive(status.data);
  const model = useGetReplayModel(replayId, {
    query: { staleTime: 0, refetchInterval: status.data?.state === "running" ? 1500 : false },
  });

  // Fetch the final model once the replay stops.
  const state = status.data?.state;
  useEffect(() => {
    if (state && !ACTIVE.has(state)) {
      queryClient.invalidateQueries({ queryKey: getGetReplayModelQueryKey(replayId) });
    }
  }, [state, replayId, queryClient]);

  if (!status.data) {
    return (
      <Center h="100%">
        <Loader />
      </Center>
    );
  }
  const replay = status.data;
  const algorithm = findAlgorithm(catalog, replay.algorithm);
  const label = (path: string) => {
    const [name, ...rest] = path.split("/");
    const buffer = algorithm?.buffers.find((b) => b.name === name);
    return rest.length ? `${buffer?.label ?? name} · ${rest.join("/")}` : (buffer?.label ?? name);
  };

  return (
    <Stack gap={0} h="100%">
      <ReplayToolbar replay={replay} active={active} />
      {replay.error && (
        <Alert color="red" title="The replay failed" m="sm">
          {replay.error}
        </Alert>
      )}
      <BufferFill buffers={replay.buffers} fill={replay.fill} label={label} />
      <Box flex={1} mih={0} pos="relative" style={{ borderTop: "1px solid var(--mantine-color-default-border)" }}>
        {model.data ? (
          <>
            <Badge variant="default" pos="absolute" top={8} left={8} style={{ zIndex: 2 }}>
              {model.data.model_label} after item {formatCount(model.data.position)}
            </Badge>
            <Visualization visualization={model.data.visualization as VisualizationsType} />
          </>
        ) : (
          <Center h="100%">
            <Loader size="sm" />
          </Center>
        )}
      </Box>
    </Stack>
  );
}

function isActive(replay: ReplayStatus | undefined) {
  return replay === undefined || ACTIVE.has(replay.state);
}

function ReplayToolbar({ replay, active }: { replay: ReplayStatus; active: boolean }) {
  const queryClient = useQueryClient();
  const control = useControlReplay({
    mutation: { onSuccess: (data) => queryClient.setQueryData(getGetReplayQueryKey(replay.id), data) },
  });
  const save = useSaveReplayModel();
  const send = (action: "pause" | "resume" | "cancel" | "speed", speed?: number) =>
    control.mutate({ replayId: replay.id, data: { action, speed } });
  const progress = replay.total ? (100 * replay.position) / replay.total : 0;

  return (
    <Group gap="sm" px="sm" py={8} wrap="wrap" style={{ borderBottom: "1px solid var(--mantine-color-default-border)" }}>
      <Text fw={600} size="sm" truncate maw={260}>
        {replay.name}
      </Text>
      <Badge color={STATE_COLORS[replay.state]} variant="light" style={{ flexShrink: 0 }}>
        {replay.state}
      </Badge>
      <Stack gap={2} flex={1} miw={220}>
        <Progress value={progress} size="sm" animated={replay.state === "running"} />
        <Text size="xs" c="dimmed">
          item {formatCount(replay.position)} of {formatCount(replay.total)}
          {replay.items_per_second !== null && ` · ${formatCount(replay.items_per_second)} items/s`} · memory{" "}
          {formatCount(replay.memory)} entries
        </Text>
      </Stack>
      <Group gap="xs" wrap="nowrap">
      <SegmentedControl
        size="xs"
        data={SPEEDS}
        value={String(replay.speed)}
        disabled={!active}
        onChange={(value) => send("speed", Number(value))}
      />
      {replay.state === "paused" ? (
        <Tooltip label="Resume">
          <ActionIcon variant="default" onClick={() => send("resume")} aria-label="Resume">
            <PlayIcon size={16} />
          </ActionIcon>
        </Tooltip>
      ) : (
        <Tooltip label="Pause">
          <ActionIcon variant="default" disabled={replay.state !== "running"} onClick={() => send("pause")} aria-label="Pause">
            <PauseIcon size={16} />
          </ActionIcon>
        </Tooltip>
      )}
      <Tooltip label="Stop">
        <ActionIcon variant="default" disabled={!active} onClick={() => send("cancel")} aria-label="Stop">
          <SquareIcon size={16} />
        </ActionIcon>
      </Tooltip>
      <Tooltip label={save.isSuccess ? "Saved as a resource" : "Save the current model as a resource"}>
        <ActionIcon
          variant="default"
          loading={save.isPending}
          onClick={() => save.mutate({ replayId: replay.id })}
          aria-label="Save model"
        >
          <SaveIcon size={16} />
        </ActionIcon>
      </Tooltip>
      </Group>
    </Group>
  );
}
