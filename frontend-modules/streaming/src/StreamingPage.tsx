import { Center, Loader, Stack } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { useCurrentOcel } from "@ocelescope/core";
import { useState } from "react";
import { useListAlgorithms } from "./api/streaming";
import { RunModel } from "./runs/RunModel";
import { RunsMenu } from "./runs/RunsMenu";
import { RunToolbar } from "./runs/RunToolbar";
import { useRunActions, useRuns } from "./runs/useRuns";
import { defaults, type Values } from "./settings/schema";
import { SettingsDrawer } from "./settings/SettingsDrawer";

/** A toolbar to configure and start runs on the current log; below it, the shown run's model. */
export default function StreamingPage() {
  const { id: ocelId } = useCurrentOcel();
  const algorithms = useListAlgorithms();
  const runs = useRuns(ocelId);
  const actions = useRunActions();
  const [settingsOpened, settings] = useDisclosure();
  const [algorithmKey, setAlgorithmKey] = useState<string>();
  const [values, setValues] = useState<Record<string, Values>>({});
  const [selectedId, setSelectedId] = useState<string>();

  if (!algorithms.data || !runs.data) {
    return (
      <Center h="100%">
        <Loader />
      </Center>
    );
  }
  const algorithm = algorithms.data.find(({ key }) => key === algorithmKey) ?? algorithms.data[0];
  const config = algorithm && (values[algorithm.key] ?? defaults(algorithm.config_schema));
  const run = runs.data.find(({ id }) => id === selectedId) ?? runs.data[0];

  const start = () =>
    algorithm &&
    ocelId &&
    actions.start.mutate(
      { data: { ocel_id: ocelId, algorithm: algorithm.key, config } },
      { onSuccess: (started) => setSelectedId(started.id) },
    );

  return (
    <Stack h="100%" gap={0}>
      <RunToolbar
        algorithms={algorithms.data}
        algorithm={algorithm}
        onAlgorithm={setAlgorithmKey}
        onSettings={settings.open}
        run={run}
        onStart={start}
        onCancel={() => run && actions.cancel.mutate({ runId: run.id })}
      >
        <RunsMenu
          runs={runs.data}
          selectedId={run?.id}
          onSelect={setSelectedId}
          onDelete={(runId) => actions.remove.mutate({ runId })}
        />
      </RunToolbar>
      <div style={{ flex: 1, minHeight: 0 }}>
        <RunModel run={run} />
      </div>
      {algorithm && (
        <SettingsDrawer
          algorithm={algorithm}
          values={config}
          onChange={(next) => setValues({ ...values, [algorithm.key]: next })}
          opened={settingsOpened}
          onClose={settings.close}
        />
      )}
    </Stack>
  );
}
