import { Alert, Center, Loader, Text } from "@mantine/core";
import { Visualization } from "@ocelescope/resources";
import type { ComponentProps } from "react";
import type { RunSummary } from "../api/streaming";
import LiveGraph from "../graph";
import { useFrame, useLayout } from "./useRuns";

type VisualizationData = ComponentProps<typeof Visualization>["visualization"];

/** The run's model as it stands after the latest item. */
export function RunModel({ run }: { run: RunSummary | undefined }) {
  const frame = useFrame(run);
  const layout = useLayout(run);
  if (!run) return <Hint>Choose an algorithm and start a run. Its model appears here item by item.</Hint>;
  if (run.error) {
    return (
      <Center h="100%" p="md">
        <Alert color="red" title="The run failed" maw={560}>
          {run.error}
        </Alert>
      </Center>
    );
  }
  if (run.phase === "layout") {
    return <Hint>Preparing the layout: the algorithm runs once at full speed, so every element gets its final place.</Hint>;
  }
  if (!frame.data || layout.isPending) {
    return (
      <Center h="100%">
        <Loader />
      </Center>
    );
  }
  if (!frame.data.visualization) {
    return <Hint>{frame.data.position === 0 ? "Waiting for the first item…" : "This model has no visualization."}</Hint>;
  }
  const visualization = frame.data.visualization as VisualizationData;
  // Graphs go to our copy of Ocelescope's graph viewer, which keeps up with a changing model.
  if (visualization.type === "graph") {
    const fixed = layout.data?.visualization as Extract<VisualizationData, { type: "graph" }> | null | undefined;
    return <LiveGraph key={run.id} visualization={visualization} layout={fixed ?? undefined} />;
  }
  return <Visualization visualization={visualization} />;
}

function Hint({ children }: { children: string }) {
  return (
    <Center h="100%" p="md">
      <Text c="dimmed">{children}</Text>
    </Center>
  );
}
