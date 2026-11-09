import { Box, Splitter, Stack } from "@mantine/core";
import type { UseSplitterReturnValue } from "@mantine/hooks";
import { useRef, useState } from "react";
import { RunSidebar } from "../features/run-config/components/RunSidebar";
import { RunCanvas } from "../features/runs/components/RunCanvas";
import { RunSummaryBar } from "../features/runs/components/RunSummaryBar";
import { BufferSizePlots } from "../features/runs/components/BufferSizePlots";
import { RunToolbar } from "../features/runs/components/RunToolbar";
import { useBufferLabel } from "../features/runs/hooks/useBufferLabel";
import { useRuns } from "../features/runs/hooks/useRuns";
import type { ModelView } from "../features/runs/lib/modelView";

/**
 * Streaming runs, laid out like Ocelescope's discovery page: the selected run's models fill the
 * canvas, the run configuration sits in a collapsible panel on the right.
 */
export default function StreamingPage() {
  const splitterRef = useRef<UseSplitterReturnValue>(null);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [view, setView] = useState<ModelView>("streaming");
  const runs = useRuns();

  const selected = runs.data?.find((run) => run.id === selectedRunId) ?? runs.data?.[0];
  const bufferLabel = useBufferLabel(selected?.config.algorithm ?? "");

  return (
    <Splitter
      splitterRef={splitterRef}
      withHandle={false}
      h="100%"
      lineSize={2}
      handleColor="var(--mantine-color-default-border)"
    >
      <Splitter.Pane defaultSize={70}>
        <Stack gap={0} h="100%">
          <RunToolbar
            runs={runs.data ?? []}
            selected={selected}
            onSelect={setSelectedRunId}
            view={view}
            onViewChange={setView}
            onToggleSettings={() => splitterRef.current?.toggleCollapse(1)}
          />
          {selected?.result && <RunSummaryBar run={selected} result={selected.result} />}
          {selected?.result?.buffer_sizes && (
            <BufferSizePlots series={selected.result.buffer_sizes} bufferLabel={bufferLabel} />
          )}
          <Box flex={1} mih={0} pos="relative">
            <RunCanvas run={selected} view={view} isLoading={runs.isPending} />
          </Box>
        </Stack>
      </Splitter.Pane>
      <Splitter.Pane defaultSize={30} min="300px" max="500px" collapsible>
        <RunSidebar onStarted={(run) => setSelectedRunId(run.id)} />
      </Splitter.Pane>
    </Splitter>
  );
}
