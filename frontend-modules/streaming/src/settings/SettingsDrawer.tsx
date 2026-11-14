import { Button, Drawer, Group } from "@mantine/core";
import type { AlgorithmInfo } from "../api/streaming";
import { defaults, type Values } from "./schema";
import { SettingsFields } from "./SettingsFields";

type Props = {
  algorithm: AlgorithmInfo;
  values: Values;
  onChange: (values: Values) => void;
  opened: boolean;
  onClose: () => void;
};

/** The selected algorithm's settings, generated from its schema. */
export function SettingsDrawer({ algorithm, values, onChange, opened, onClose }: Props) {
  return (
    <Drawer position="right" size="sm" opened={opened} onClose={onClose} title={algorithm.label}>
      <SettingsFields schema={algorithm.config_schema} values={values} onChange={onChange} />
      <Group justify="flex-end" mt="xl">
        <Button variant="subtle" onClick={() => onChange(defaults(algorithm.config_schema))}>
          Reset to defaults
        </Button>
      </Group>
    </Drawer>
  );
}
