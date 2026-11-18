import { Alert, Center, Loader, Stack } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { useCurrentOcel } from "@ocelescope/core";
import { useState } from "react";
import { type Pace, useListAlgorithms, useListHeuristics } from "./api/streaming";
import { PaceControls } from "./runs/PaceControls";
import { RunModel } from "./runs/RunModel";
import { RunsMenu } from "./runs/RunsMenu";
import { RunToolbar } from "./runs/RunToolbar";
import { isActive, useRunActions, useRuns } from "./runs/useRuns";
import { bounds } from "./settings/BufferFields";
import { type Settings, SettingsDrawer, settingsDefaults } from "./settings/SettingsDrawer";

/** A toolbar to configure and start runs on the current log; below it, the shown run's model. */
export default function StreamingPage() {
  const { id: ocelId } = useCurrentOcel();
  const algorithms = useListAlgorithms();
  const heuristics = useListHeuristics();
  const runs = useRuns(ocelId);
  const actions = useRunActions();
  const [settingsOpened, drawer] = useDisclosure();
  const [algorithmKey, setAlgorithmKey] = useState<string>();
  const [settingsByKey, setSettingsByKey] = useState<Record<string, Settings>>({});
  const [selectedId, setSelectedId] = useState<string>();
  const [pace, setPace] = useState<Pace>({ rate: 25, paused: false });

  if (!algorithms.data || !heuristics.data || !runs.data) {
    return (
      <Center h="100%">
        <Loader />
      </Center>
    );
  }
  const algorithm = algorithms.data.find(({ key }) => key === algorithmKey) ?? algorithms.data[0];
  const settings = algorithm && (settingsByKey[algorithm.key] ?? settingsDefaults(algorithm));
  const run = runs.data.find(({ id }) => id === selectedId) ?? runs.data[0];

  const start = () =>
    algorithm &&
    settings &&
    ocelId &&
    actions.start.mutate(
      {
        data: {
          ocel_id: ocelId,
          algorithm: algorithm.key,
          config: settings.config,
          buffers: bounds(settings.buffers),
          pace,
          fixed_layout: pace.paused || pace.rate != null, // watched runs: one extra pass at full speed
        },
      },
      { onSuccess: (started) => setSelectedId(started.id) },
    );

  const active = run !== undefined && isActive(run);
  const changePace = (next: Pace) => {
    setPace(next);
    if (run && active) actions.pace.mutate({ runId: run.id, data: next });
  };

  return (
    <Stack h="100%" gap={0}>
      <RunToolbar
        algorithms={algorithms.data}
        algorithm={algorithm}
        onAlgorithm={setAlgorithmKey}
        onSettings={drawer.open}
        run={run}
        onStart={start}
        onCancel={() => run && actions.cancel.mutate({ runId: run.id })}
        controls={
          <PaceControls
            pace={pace}
            onPace={changePace}
            onStep={run && active && pace.paused ? () => actions.step.mutate({ runId: run.id }) : undefined}
          />
        }
      >
        <RunsMenu
          runs={runs.data}
          selectedId={run?.id}
          onSelect={setSelectedId}
          onDelete={(runId) => actions.remove.mutate({ runId })}
        />
      </RunToolbar>
      {actions.start.error && (
        <Alert color="red" m="xs" withCloseButton onClose={actions.start.reset} title="The run could not start">
          {reason(actions.start.error)}
        </Alert>
      )}
      <div style={{ flex: 1, minHeight: 0 }}>
        <RunModel run={run} />
      </div>
      {algorithm && settings && (
        <SettingsDrawer
          algorithm={algorithm}
          heuristics={heuristics.data}
          settings={settings}
          onChange={(next) => setSettingsByKey({ ...settingsByKey, [algorithm.key]: next })}
          opened={settingsOpened}
          onClose={drawer.close}
        />
      )}
    </Stack>
  );
}

/** The API's explanation of a rejected request, e.g. an invalid buffer setting. */
function reason(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((issue: { msg?: string }) => issue.msg).join("; ");
  return String(error);
}
