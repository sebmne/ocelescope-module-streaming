import { Group, Text, Tooltip } from "@mantine/core";
import { InfoIcon } from "lucide-react";
import type { ReactNode } from "react";

type LabelWithInfoProps = {
  label: ReactNode;
  info: ReactNode;
};

/** A form label followed by an info icon that explains it in a tooltip. */
export function LabelWithInfo({ label, info }: LabelWithInfoProps) {
  return (
    <Group gap={6} wrap="nowrap" component="span" display="inline-flex">
      <Text span size="sm" fw={500}>
        {label}
      </Text>
      <Tooltip label={info} multiline w={280} withArrow>
        <InfoIcon size={14} color="var(--mantine-color-dimmed)" style={{ flexShrink: 0 }} />
      </Tooltip>
    </Group>
  );
}
