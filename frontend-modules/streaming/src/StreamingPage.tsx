import { Alert, Box, LoadingOverlay, Splitter, Stack } from "@mantine/core";
import type { UseSplitterReturnValue } from "@mantine/hooks";
import { useCurrentOcel } from "@ocelescope/core";
import { useRef, useState } from "react";
import { useGetCatalog } from "./api/streaming";
import { ConfigPanel } from "./config/ConfigPanel";
import { RunBar, type View } from "./runs/RunBar";
import { RunView } from "./runs/RunView";
import { useRuns } from "./runs/useRuns";

/** Laid out like Ocelescope's discovery page: the run in the center, its configuration on the right. */
export default function StreamingPage() {
  const splitter = useRef<UseSplitterReturnValue>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [view, setView] = useState<View>("model");
  const { id: ocelId } = useCurrentOcel();
  const catalog = useGetCatalog();
  const runs = useRuns();
  const run = runs.data?.find(({ id }) => id === selectedId) ?? runs.data?.[0];

  return (
    <Splitter splitterRef={splitter} withHandle={false} h="100%" lineSize={2} handleColor="var(--mantine-color-default-border)">
      <Splitter.Pane defaultSize={70}>
        <Stack gap={0} h="100%">
          <RunBar
            runs={runs.data ?? []}
            run={run}
            onSelect={setSelectedId}
            view={view}
            onView={setView}
            onToggleSettings={() => splitter.current?.toggleCollapse(1)}
          />
          <Box flex={1} mih={0} pos="relative">
            {runs.isPending ? <LoadingOverlay visible /> : <RunView run={run} view={view} />}
          </Box>
        </Stack>
      </Splitter.Pane>
      <Splitter.Pane defaultSize={30} min="300px" max="500px" collapsible>
        {catalog.isPending && <LoadingOverlay visible />}
        {catalog.data && catalog.data.algorithms.length === 0 && (
          <Alert m="md" title="No algorithms registered">
            Add one in backend-modules/streaming/.../algorithms.
          </Alert>
        )}
        {catalog.data && catalog.data.algorithms.length > 0 && ocelId && (
          <ConfigPanel key={ocelId} catalog={catalog.data} ocelId={ocelId} onStarted={(started) => setSelectedId(started.id)} />
        )}
      </Splitter.Pane>
    </Splitter>
  );
}
