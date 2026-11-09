import { Select, Stack } from "@mantine/core";
import type { AlgorithmInfo } from "../../../api/streaming";
import { LabelWithInfo } from "../../../components/LabelWithInfo";
import { hasParameters, SchemaForm } from "../../../components/SchemaForm";
import { type Params, sortAlgorithms } from "../model";

type AlgorithmSectionProps = {
  algorithms: AlgorithmInfo[];
  selected: AlgorithmInfo;
  params: Params;
  onSelect: (algorithm: AlgorithmInfo) => void;
  onParamsChange: (params: Params) => void;
};

/** The target model: algorithms grouped by the kind of model they discover. */
export function AlgorithmSection({ algorithms, selected, params, onSelect, onParamsChange }: AlgorithmSectionProps) {
  const sorted = sortAlgorithms(algorithms);
  const models = [...new Set(sorted.map((algorithm) => algorithm.model))];
  return (
    <Stack gap="xs">
      <Select
        label={<LabelWithInfo label="Target model" info={selected.description} />}
        data={models.map((model) => ({
          group: model,
          items: sorted
            .filter((algorithm) => algorithm.model === model)
            .map((algorithm) => ({ value: algorithm.key, label: algorithm.label })),
        }))}
        value={selected.key}
        allowDeselect={false}
        onChange={(key) => {
          const algorithm = algorithms.find((candidate) => candidate.key === key);
          if (algorithm) onSelect(algorithm);
        }}
      />
      {hasParameters(selected.params_schema) && (
        <SchemaForm schema={selected.params_schema} value={params} onChange={onParamsChange} />
      )}
    </Stack>
  );
}
