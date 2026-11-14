import { ActionIcon, Group, Select, Tooltip } from "@mantine/core";
import { PauseIcon, PlayIcon, StepForwardIcon } from "lucide-react";
import type { Pace } from "../api/streaming";

const SPEEDS = [
  { value: "1", label: "1 / s" },
  { value: "5", label: "5 / s" },
  { value: "25", label: "25 / s" },
  { value: "100", label: "100 / s" },
  { value: "max", label: "Max" },
];

type Props = { pace: Pace; onPace: (pace: Pace) => void; onStep: (() => void) | undefined };

/** Pause, single steps and items per second; they apply to the next run and to the running one. */
export function PaceControls({ pace, onPace, onStep }: Props) {
  return (
    <Group gap={4} wrap="nowrap">
      <Tooltip label={pace.paused ? "Resume" : "Pause"}>
        <ActionIcon
          variant="default"
          size="input-sm"
          aria-label={pace.paused ? "Resume" : "Pause"}
          onClick={() => onPace({ ...pace, paused: !pace.paused })}
        >
          {pace.paused ? <PlayIcon size={16} /> : <PauseIcon size={16} />}
        </ActionIcon>
      </Tooltip>
      <Tooltip label="Next item">
        <ActionIcon variant="default" size="input-sm" aria-label="Next item" disabled={!onStep} onClick={onStep}>
          <StepForwardIcon size={16} />
        </ActionIcon>
      </Tooltip>
      <Select
        aria-label="Speed"
        data={SPEEDS}
        value={pace.rate ? String(pace.rate) : "max"}
        onChange={(value) => onPace({ ...pace, rate: value === "max" ? null : Number(value) })}
        allowDeselect={false}
        w={96}
      />
    </Group>
  );
}
