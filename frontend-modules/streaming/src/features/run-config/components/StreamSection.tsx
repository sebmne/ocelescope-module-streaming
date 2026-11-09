import { Checkbox, Stack } from "@mantine/core";
import type { StreamSettings } from "../../../api/streaming";

type StreamSectionProps = {
  stream: Required<StreamSettings>;
  onChange: (stream: Partial<StreamSettings>) => void;
};

const ITEM_KINDS: { key: keyof StreamSettings; label: string }[] = [
  { key: "events", label: "Events" },
  { key: "object_to_object", label: "Object-to-object updates" },
  { key: "attribute_updates", label: "Attribute updates" },
];

export function StreamSection({ stream, onChange }: StreamSectionProps) {
  return (
    <Checkbox.Group
      label="Stream items"
      description="Positions count every replayed item, which affects position-based heuristics."
      value={ITEM_KINDS.filter(({ key }) => stream[key]).map(({ key }) => key)}
      onChange={(selected) =>
        onChange(Object.fromEntries(ITEM_KINDS.map(({ key }) => [key, selected.includes(key)])))
      }
    >
      <Stack gap={6} mt="xs">
        {ITEM_KINDS.map(({ key, label }) => (
          <Checkbox key={key} value={key} label={label} />
        ))}
      </Stack>
    </Checkbox.Group>
  );
}
