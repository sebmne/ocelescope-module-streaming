import { Chip, Group, Stack } from "@mantine/core";
import type { StreamSettings } from "../../../api/streaming";
import { LabelWithInfo } from "../../../components/LabelWithInfo";

type StreamSectionProps = {
  stream: Required<StreamSettings>;
  onChange: (stream: Partial<StreamSettings>) => void;
};

const ITEM_KINDS: { key: keyof StreamSettings; label: string }[] = [
  { key: "events", label: "Events" },
  { key: "object_to_object", label: "O2O updates" },
  { key: "attribute_updates", label: "Attribute updates" },
];

/** Which kinds of items the replayed stream contains. */
export function StreamSection({ stream, onChange }: StreamSectionProps) {
  return (
    <Stack gap={6}>
      <LabelWithInfo
        label="Stream items"
        info="The log is replayed as a stream of these item kinds, ordered by time. The algorithm's default is preselected. Ages and deadlines of heuristics count every replayed item, so adding item kinds changes them."
      />
      <Chip.Group
        multiple
        value={ITEM_KINDS.filter(({ key }) => stream[key]).map(({ key }) => key)}
        onChange={(selected) => onChange(Object.fromEntries(ITEM_KINDS.map(({ key }) => [key, selected.includes(key)])))}
      >
        <Group gap={6}>
          {ITEM_KINDS.map(({ key, label }) => (
            <Chip key={key} value={key} size="xs">
              {label}
            </Chip>
          ))}
        </Group>
      </Chip.Group>
    </Stack>
  );
}
