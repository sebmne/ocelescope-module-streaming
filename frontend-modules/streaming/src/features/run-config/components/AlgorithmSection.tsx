import { Select, Stack, Text } from "@mantine/core";
import type { AlgorithmInfo } from "../../../api/streaming";
import { SchemaForm } from "../../../components/SchemaForm";
import type { Params } from "../model";

type AlgorithmSectionProps = {
  algorithms: AlgorithmInfo[];
  selected: AlgorithmInfo;
  params: Params;
  onSelect: (algorithm: AlgorithmInfo) => void;
  onParamsChange: (params: Params) => void;
};

export function AlgorithmSection({ algorithms, selected, params, onSelect, onParamsChange }: AlgorithmSectionProps) {
  return (
    <Stack gap="xs">
      <Select
        label="Algorithm"
        data={algorithms.map((algorithm) => ({ value: algorithm.key, label: algorithm.label }))}
        value={selected.key}
        allowDeselect={false}
        onChange={(key) => {
          const algorithm = algorithms.find((candidate) => candidate.key === key);
          if (algorithm) onSelect(algorithm);
        }}
      />
      <Text size="sm" c="dimmed">
        {selected.description}
      </Text>
      <SchemaForm schema={selected.params_schema} value={params} onChange={onParamsChange} />
    </Stack>
  );
}
