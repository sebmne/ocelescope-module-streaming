import { Button, Drawer, Group, Stack } from "@mantine/core";
import type { AlgorithmInfo, HeuristicInfo } from "../api/streaming";
import { BufferFields, type BufferValues } from "./BufferFields";
import { defaults, properties, type Values } from "./schema";
import { SettingsFields } from "./SettingsFields";

/** An algorithm's settings and, for buffer-based ones, each buffer's capacity and heuristic. */
export type Settings = { config: Values; buffers: Record<string, BufferValues> };

export const settingsDefaults = (algorithm: AlgorithmInfo): Settings => ({
  config: defaults(algorithm.config_schema),
  buffers: {},
});

type Props = {
  algorithm: AlgorithmInfo;
  heuristics: HeuristicInfo[];
  settings: Settings;
  onChange: (settings: Settings) => void;
  opened: boolean;
  onClose: () => void;
};

/** The selected algorithm's settings, generated from its schemas. */
export function SettingsDrawer({ algorithm, heuristics, settings, onChange, opened, onClose }: Props) {
  return (
    <Drawer position="right" size="sm" opened={opened} onClose={onClose} title={algorithm.label}>
      <Stack gap="xl">
        {properties(algorithm.config_schema).length > 0 && (
          <SettingsFields
            schema={algorithm.config_schema}
            values={settings.config}
            onChange={(config) => onChange({ ...settings, config })}
          />
        )}
        {algorithm.buffers.length > 0 && (
          <BufferFields
            algorithm={algorithm}
            heuristics={heuristics}
            values={settings.buffers}
            onChange={(buffers) => onChange({ ...settings, buffers })}
          />
        )}
      </Stack>
      <Group justify="flex-end" mt="xl">
        <Button variant="subtle" onClick={() => onChange(settingsDefaults(algorithm))}>
          Reset to defaults
        </Button>
      </Group>
    </Drawer>
  );
}
