import { Alert, Box, LoadingOverlay } from "@mantine/core";
import { useCurrentOcel } from "@ocelescope/core";
import { type RunSummary, useGetCatalog } from "../../../api/streaming";
import { RunForm } from "./RunForm";

type RunSidebarProps = {
  onStarted: (run: RunSummary) => void;
};

/** The configuration panel: loads the catalog and the current log, then shows the run form. */
export function RunSidebar({ onStarted }: RunSidebarProps) {
  const { id: ocelId } = useCurrentOcel();
  const catalog = useGetCatalog();

  if (catalog.isPending) {
    return (
      <Box pos="relative" h="100%">
        <LoadingOverlay visible />
      </Box>
    );
  }
  if (catalog.isError) {
    return <Alert m="md" color="red" title="Could not load the available algorithms" />;
  }
  if (catalog.data.algorithms.length === 0) {
    return <Alert m="md" color="yellow" title="No streaming algorithms are available" />;
  }
  if (!ocelId) {
    return <Alert m="md" title="Select an event log to configure a run" />;
  }
  // Remount per log, so a new log starts with a fresh form.
  return <RunForm key={ocelId} catalog={catalog.data} ocelId={ocelId} onStarted={onStarted} />;
}
