import { Badge, Box, Splitter } from "@mantine/core";
import { ResourceViewer } from "@ocelescope/resources";
import type { RunResult } from "../../../api/streaming";
import type { ModelView } from "../lib/modelView";

type ModelCanvasProps = {
  result: RunResult;
  view: ModelView;
};

/** The streaming model, the offline reference, or both side by side. */
export function ModelCanvas({ result, view }: ModelCanvasProps) {
  if (view !== "both") {
    const id = view === "streaming" ? result.streaming_resource_id : result.offline_resource_id;
    return <ResourceViewer key={id} id={id} />;
  }
  return (
    <Splitter h="100%" lineSize={4} handleColor="var(--mantine-color-default-border)">
      <Splitter.Pane defaultSize={50} min="15%">
        <LabeledModel label="Streaming" id={result.streaming_resource_id} />
      </Splitter.Pane>
      <Splitter.Pane defaultSize={50} min="15%">
        <LabeledModel label="Offline reference" id={result.offline_resource_id} />
      </Splitter.Pane>
    </Splitter>
  );
}

function LabeledModel({ label, id }: { label: string; id: string }) {
  return (
    <Box h="100%" pos="relative">
      <Badge variant="default" pos="absolute" top={8} left={8} style={{ zIndex: 2 }}>
        {label}
      </Badge>
      <ResourceViewer id={id} />
    </Box>
  );
}
