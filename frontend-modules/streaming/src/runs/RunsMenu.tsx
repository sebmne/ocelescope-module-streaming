import { ActionIcon, Badge, Button, Group, Menu, Text } from "@mantine/core";
import { HistoryIcon, Trash2Icon } from "lucide-react";
import type { RunSummary } from "../api/streaming";
import { isActive } from "./useRuns";

const STATE_COLORS: Record<string, string> = { STARTED: "blue", SUCCESS: "green", FAILURE: "red", CANCELLED: "orange" };

type Props = { runs: RunSummary[]; selectedId: string | undefined; onSelect: (id: string) => void; onDelete: (id: string) => void };

/** Earlier runs on this log: select one to show it, or delete it. */
export function RunsMenu({ runs, selectedId, onSelect, onDelete }: Props) {
  return (
    <Menu position="bottom-end" width={360} withinPortal>
      <Menu.Target>
        <Button variant="default" leftSection={<HistoryIcon size={16} />} disabled={runs.length === 0}>
          Runs
        </Button>
      </Menu.Target>
      <Menu.Dropdown>
        {runs.map((run) => (
          <Menu.Item
            key={run.id}
            onClick={() => onSelect(run.id)}
            styles={{ itemLabel: { minWidth: 0 } }}
            bg={run.id === selectedId ? "var(--mantine-color-default-hover)" : undefined}
            rightSection={
              <ActionIcon
                component="div"
                variant="subtle"
                color="gray"
                size="sm"
                aria-label="Delete run"
                disabled={isActive(run)}
                onClick={(event) => {
                  event.stopPropagation();
                  onDelete(run.id);
                }}
              >
                <Trash2Icon size={14} />
              </ActionIcon>
            }
          >
            <Group gap="xs" wrap="nowrap">
              <Text size="sm" truncate flex={1}>
                {run.name}
              </Text>
              <Badge size="xs" variant="light" color={STATE_COLORS[run.state] ?? "gray"}>
                {run.state.toLowerCase()}
              </Badge>
            </Group>
          </Menu.Item>
        ))}
      </Menu.Dropdown>
    </Menu>
  );
}
