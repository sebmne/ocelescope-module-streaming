import { Select, Text } from "@mantine/core";
import type { AlgorithmInfo, Preset } from "../../../api/streaming";

type PresetSectionProps = {
  presets: Preset[];
  algorithms: AlgorithmInfo[];
  selected: string | null;
  onApply: (preset: Preset, algorithm: AlgorithmInfo) => void;
};

/** Fills the form with the configuration of a published technique. Editing the form clears it. */
export function PresetSection({ presets, algorithms, selected, onApply }: PresetSectionProps) {
  const available = presets.filter((preset) => algorithms.some((algorithm) => algorithm.key === preset.algorithm));
  if (available.length === 0) return null;
  const current = available.find((preset) => preset.key === selected);
  return (
    <div>
      <Select
        label="Preset"
        placeholder="Custom configuration"
        data={available.map((preset) => ({ value: preset.key, label: preset.label }))}
        value={selected}
        clearable={false}
        onChange={(key) => {
          const preset = available.find((candidate) => candidate.key === key);
          const algorithm = algorithms.find((candidate) => candidate.key === preset?.algorithm);
          if (preset && algorithm) onApply(preset, algorithm);
        }}
      />
      {current && (
        <Text size="xs" c="dimmed" mt={4}>
          {current.description}
        </Text>
      )}
    </div>
  );
}
