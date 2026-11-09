import type {
  AlgorithmInfo,
  BufferSetting,
  EvictionMode,
  HeuristicInfo,
  Preset,
  RunConfig,
  StreamSettings,
} from "../../api/streaming";

/** The order in which kinds of models are offered; other kinds follow alphabetically. */
const MODEL_ORDER = ["Process tree", "DF2 graph", "OC-DFG", "TOTeM"];

/** Algorithms ordered by kind of model, keeping the catalog order within a kind. */
export function sortAlgorithms(algorithms: AlgorithmInfo[]): AlgorithmInfo[] {
  const rank = (model: string) => {
    const index = MODEL_ORDER.indexOf(model);
    return index === -1 ? MODEL_ORDER.length : index;
  };
  return [...algorithms].sort((a, b) => rank(a.model) - rank(b.model) || a.model.localeCompare(b.model));
}

/** Default capacity offered when a buffer gets a fixed capacity. */
export const DEFAULT_CAPACITY = 1000;

export type Params = Record<string, unknown>;

/** How a buffer evicts: never, or in one of the backend's eviction modes. */
export type BufferMode = "unbounded" | EvictionMode;

export const BUFFER_MODES: { value: BufferMode; label: string; description: string }[] = [
  { value: "unbounded", label: "Unbounded", description: "Keeps every entry; never evicts." },
  {
    value: "capacity",
    label: "Capacity",
    description: "Holds at most a fixed number of entries. When full, the heuristic picks the entry to evict.",
  },
  {
    value: "expiry",
    label: "Schedule",
    description: "No size limit. The heuristic decides when each entry expires, e.g. after a period of inactivity.",
  },
  {
    value: "both",
    label: "Both",
    description: "Entries expire on the heuristic's schedule, and the size is limited as well.",
  },
];

/** Whether a mode limits the number of entries. */
export const hasCapacity = (mode: BufferMode) => mode === "capacity" || mode === "both";

export type BufferFormState = {
  mode: BufferMode;
  capacity: number;
  heuristic: string | null;
  heuristicParams: Params;
};

export type RunFormState = {
  algorithm: string;
  algorithmParams: Params;
  stream: Required<StreamSettings>;
  buffers: Record<string, BufferFormState>;
  name: string;
  preset: string | null;
  monitorBuffers: boolean;
};

export type RunFormAction =
  | { type: "selectAlgorithm"; algorithm: AlgorithmInfo }
  | { type: "applyPreset"; preset: Preset; algorithm: AlgorithmInfo }
  | { type: "setAlgorithmParams"; params: Params }
  | { type: "setStream"; stream: Partial<StreamSettings> }
  | { type: "updateBuffer"; buffer: string; patch: Partial<BufferFormState> }
  | { type: "updateBuffers"; buffers: string[]; patch: Partial<BufferFormState> }
  | { type: "setName"; name: string }
  | { type: "setMonitorBuffers"; monitorBuffers: boolean };

const unboundedBuffer = (): BufferFormState => ({
  mode: "unbounded",
  capacity: DEFAULT_CAPACITY,
  heuristic: null,
  heuristicParams: {},
});

function streamOf(settings: StreamSettings): Required<StreamSettings> {
  return {
    events: settings.events ?? true,
    object_to_object: settings.object_to_object ?? false,
    attribute_updates: settings.attribute_updates ?? false,
  };
}

/** The form state of a buffer configured by a preset, mirroring the backend's mode derivation. */
function bufferFromSetting(setting: BufferSetting): BufferFormState {
  if (!setting.heuristic) return unboundedBuffer();
  const capacity = setting.capacity ?? null;
  return {
    mode: setting.mode ?? (capacity !== null ? "capacity" : "expiry"),
    capacity: capacity ?? DEFAULT_CAPACITY,
    heuristic: setting.heuristic,
    heuristicParams: (setting.heuristic_params ?? {}) as Params,
  };
}

/** The form state for a freshly selected algorithm: its default stream, all buffers unbounded. */
export function initialRunForm(algorithm: AlgorithmInfo): RunFormState {
  return {
    algorithm: algorithm.key,
    algorithmParams: {},
    stream: streamOf(algorithm.stream),
    buffers: Object.fromEntries(algorithm.buffers.map((buffer) => [buffer.name, unboundedBuffer()])),
    name: "",
    preset: null,
    monitorBuffers: false,
  };
}

export function runFormReducer(state: RunFormState, action: RunFormAction): RunFormState {
  switch (action.type) {
    case "selectAlgorithm":
      return { ...initialRunForm(action.algorithm), name: state.name, monitorBuffers: state.monitorBuffers };
    case "applyPreset": {
      const initial = initialRunForm(action.algorithm);
      const buffers = { ...initial.buffers };
      for (const [name, setting] of Object.entries(action.preset.buffers ?? {})) {
        if (name in buffers) buffers[name] = bufferFromSetting(setting);
      }
      return {
        ...initial,
        algorithmParams: (action.preset.algorithm_params ?? {}) as Params,
        stream: action.preset.stream ? streamOf(action.preset.stream) : initial.stream,
        buffers,
        name: action.preset.label,
        preset: action.preset.key,
        monitorBuffers: state.monitorBuffers,
      };
    }
    case "setAlgorithmParams":
      return keepPresetIfUnchanged(state, { ...state, algorithmParams: action.params });
    case "setStream":
      return keepPresetIfUnchanged(state, { ...state, stream: { ...state.stream, ...action.stream } });
    case "updateBuffer":
      return keepPresetIfUnchanged(state, {
        ...state,
        buffers: { ...state.buffers, [action.buffer]: { ...state.buffers[action.buffer], ...action.patch } },
      });
    case "updateBuffers":
      return keepPresetIfUnchanged(state, {
        ...state,
        buffers: {
          ...state.buffers,
          ...Object.fromEntries(
            action.buffers.map((name) => [name, { ...state.buffers[name], ...action.patch }] as const),
          ),
        },
      });
    case "setName":
      return { ...state, name: action.name };
    case "setMonitorBuffers":
      return { ...state, monitorBuffers: action.monitorBuffers };
  }
}

/**
 * Clears the applied preset once the configuration differs from it. Parameter forms report
 * their defaults on mount, so changes that only add keys do not count as edits.
 */
function keepPresetIfUnchanged(before: RunFormState, after: RunFormState): RunFormState {
  const config = (state: RunFormState) => [state.algorithmParams, state.stream, state.buffers];
  return extends_(config(after), config(before)) ? after : { ...after, preset: null };
}

/** Whether `value` equals `base`, except for object keys that only `value` has. */
function extends_(value: unknown, base: unknown): boolean {
  if (Array.isArray(base)) {
    return Array.isArray(value) && value.length === base.length && base.every((item, i) => extends_(value[i], item));
  }
  if (base !== null && typeof base === "object") {
    if (value === null || typeof value !== "object" || Array.isArray(value)) return false;
    const record = value as Record<string, unknown>;
    return Object.entries(base).every(([key, item]) => key in record && extends_(record[key], item));
  }
  return Object.is(value, base);
}

/** The heuristics that support an eviction mode. */
export function heuristicsFor(heuristics: HeuristicInfo[], mode: BufferMode): HeuristicInfo[] {
  if (mode === "unbounded") return [];
  return heuristics.filter((heuristic) => heuristic.modes.includes(mode));
}

/** Problems that prevent starting a run, as user-facing messages. */
export function validateRunForm(state: RunFormState, heuristics: HeuristicInfo[]): string[] {
  const errors: string[] = [];
  if (!Object.values(state.stream).some(Boolean)) {
    errors.push("Select at least one kind of stream item.");
  }
  for (const [name, buffer] of Object.entries(state.buffers)) {
    if (buffer.mode === "unbounded") continue;
    if (buffer.heuristic === null) {
      errors.push(`Choose a heuristic for buffer "${name}".`);
    } else if (!heuristicsFor(heuristics, buffer.mode).some((heuristic) => heuristic.key === buffer.heuristic)) {
      errors.push(`The heuristic of buffer "${name}" does not support this eviction mode.`);
    }
  }
  return errors;
}

/** Converts the form state into the API's run configuration. */
export function toRunConfig(state: RunFormState, ocelId: string): RunConfig {
  return {
    ocel_id: ocelId,
    algorithm: state.algorithm,
    algorithm_params: state.algorithmParams,
    stream: state.stream,
    name: state.name.trim() || null,
    monitor_buffers: state.monitorBuffers,
    buffers: Object.fromEntries(
      Object.entries(state.buffers)
        .filter(([, buffer]) => buffer.mode !== "unbounded")
        .map(([name, buffer]) => [
          name,
          {
            capacity: hasCapacity(buffer.mode) ? buffer.capacity : null,
            heuristic: buffer.heuristic,
            heuristic_params: buffer.heuristicParams,
            mode: buffer.mode as EvictionMode,
          },
        ]),
    ),
  };
}
