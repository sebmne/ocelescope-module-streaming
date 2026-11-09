import type { AlgorithmInfo, RunConfig, StreamSettings } from "../../api/streaming";

/** Default capacity offered when a buffer is switched to bounded. */
export const DEFAULT_CAPACITY = 1000;

export type Params = Record<string, unknown>;

export type BufferFormState = {
  bounded: boolean;
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
};

export type RunFormAction =
  | { type: "selectAlgorithm"; algorithm: AlgorithmInfo }
  | { type: "setAlgorithmParams"; params: Params }
  | { type: "setStream"; stream: Partial<StreamSettings> }
  | { type: "updateBuffer"; buffer: string; patch: Partial<BufferFormState> }
  | { type: "setName"; name: string };

const unboundedBuffer = (): BufferFormState => ({
  bounded: false,
  capacity: DEFAULT_CAPACITY,
  heuristic: null,
  heuristicParams: {},
});

/** The form state for a freshly selected algorithm: its default stream, all buffers unbounded. */
export function initialRunForm(algorithm: AlgorithmInfo): RunFormState {
  return {
    algorithm: algorithm.key,
    algorithmParams: {},
    stream: {
      events: algorithm.stream.events ?? true,
      object_to_object: algorithm.stream.object_to_object ?? false,
      attribute_updates: algorithm.stream.attribute_updates ?? false,
    },
    buffers: Object.fromEntries(algorithm.buffers.map((buffer) => [buffer.name, unboundedBuffer()])),
    name: "",
  };
}

export function runFormReducer(state: RunFormState, action: RunFormAction): RunFormState {
  switch (action.type) {
    case "selectAlgorithm":
      return { ...initialRunForm(action.algorithm), name: state.name };
    case "setAlgorithmParams":
      return { ...state, algorithmParams: action.params };
    case "setStream":
      return { ...state, stream: { ...state.stream, ...action.stream } };
    case "updateBuffer":
      return {
        ...state,
        buffers: { ...state.buffers, [action.buffer]: { ...state.buffers[action.buffer], ...action.patch } },
      };
    case "setName":
      return { ...state, name: action.name };
  }
}

/** Problems that prevent starting a run, as user-facing messages. */
export function validateRunForm(state: RunFormState): string[] {
  const errors: string[] = [];
  if (!Object.values(state.stream).some(Boolean)) {
    errors.push("Select at least one kind of stream item.");
  }
  for (const [name, buffer] of Object.entries(state.buffers)) {
    if (buffer.bounded && buffer.heuristic === null) {
      errors.push(`Choose a heuristic for the bounded buffer "${name}".`);
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
    buffers: Object.fromEntries(
      Object.entries(state.buffers)
        .filter(([, buffer]) => buffer.bounded)
        .map(([name, buffer]) => [
          name,
          { capacity: buffer.capacity, heuristic: buffer.heuristic, heuristic_params: buffer.heuristicParams },
        ]),
    ),
  };
}
