import { ActionIcon, Group, SegmentedControl, Tooltip } from "@mantine/core";
import { SettingsIcon, SquareIcon } from "lucide-react";
import type { RunSummary } from "../../../api/streaming";
import { useCancelRunAndRefresh } from "../hooks/useRuns";
import { MODEL_VIEWS, type ModelView } from "../lib/modelView";
import { isActive } from "../lib/runState";
import { RunSelect } from "./RunSelect";
import { RunStateBadge } from "./RunStateBadge";

type RunToolbarProps = {
  runs: RunSummary[];
  selected: RunSummary | undefined;
  onSelect: (id: string) => void;
  view: ModelView;
  onViewChange: (view: ModelView) => void;
  onToggleSettings: () => void;
};

/** The bar above the canvas: run selection and state on the left, view controls on the right. */
export function RunToolbar({ runs, selected, onSelect, view, onViewChange, onToggleSettings }: RunToolbarProps) {
  const cancel = useCancelRunAndRefresh();

  return (
    <Group
      px="sm"
      py="xs"
      gap="xs"
      wrap="nowrap"
      justify="space-between"
      style={{ borderBottom: "2px solid var(--mantine-color-default-border)" }}
    >
      <Group gap="xs" wrap="nowrap" flex={1} miw={0}>
        <RunSelect runs={runs} selected={selected} onSelect={onSelect} />
        {selected && <RunStateBadge state={selected.state} />}
        {selected && isActive(selected.state) && (
          <Tooltip label="Cancel run">
            <ActionIcon
              variant="light"
              color="red"
              size="input-sm"
              loading={cancel.isPending}
              onClick={() => cancel.mutate({ runId: selected.id })}
              aria-label="Cancel run"
            >
              <SquareIcon size={16} />
            </ActionIcon>
          </Tooltip>
        )}
      </Group>
      <Group gap="xs" wrap="nowrap">
        <SegmentedControl
          size="xs"
          data={MODEL_VIEWS}
          value={view}
          onChange={(value) => onViewChange(value as ModelView)}
          disabled={!selected?.result}
        />
        <Tooltip label="Toggle settings">
          <ActionIcon variant="outline" size="input-sm" onClick={onToggleSettings} aria-label="Toggle settings">
            <SettingsIcon size={20} />
          </ActionIcon>
        </Tooltip>
      </Group>
    </Group>
  );
}
