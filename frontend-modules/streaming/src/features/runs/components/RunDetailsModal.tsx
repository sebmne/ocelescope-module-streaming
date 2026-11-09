import { Modal, Stack, Title } from "@mantine/core";
import type { RunResult } from "../../../api/streaming";
import { BufferStatsTable } from "./BufferStatsTable";
import { ScoresTable } from "./ScoresTable";

type RunDetailsModalProps = {
  title: string;
  result: RunResult;
  bufferLabel: (name: string) => string;
  opened: boolean;
  onClose: () => void;
};

export function RunDetailsModal({ title, result, bufferLabel, opened, onClose }: RunDetailsModalProps) {
  return (
    <Modal opened={opened} onClose={onClose} title={title} size="xl">
      <Stack gap="lg">
        <Stack gap="xs">
          <Title order={5}>Agreement with the offline model</Title>
          <ScoresTable scores={result.scores} />
        </Stack>
        <Stack gap="xs">
          <Title order={5}>Buffers</Title>
          <BufferStatsTable buffers={result.buffers} bufferLabel={bufferLabel} />
        </Stack>
      </Stack>
    </Modal>
  );
}
