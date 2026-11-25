import type {
  AlgorithmInfo,
  BufferConfig,
  Catalog,
  HeuristicInfo,
  Preset,
  ReplayConfig,
  StreamOptions,
} from "../api/streaming";

/** The run configuration the user edits before starting a replay. */
export type Draft = {
  presetKey: string | null;
  algorithm: string;
  params: Record<string, unknown>;
  buffers: Record<string, BufferConfig>;
  stream: StreamOptions;
  speed: number;
  trackBuffers: boolean;
};

export const SPEEDS = [
  { value: "20", label: "20/s" },
  { value: "200", label: "200/s" },
  { value: "2000", label: "2k/s" },
  { value: "20000", label: "20k/s" },
  { value: "0", label: "Max" },
];

export function findAlgorithm(catalog: Catalog, key: string): AlgorithmInfo | undefined {
  return catalog.algorithms.find((algorithm) => algorithm.key === key);
}

export function findHeuristic(catalog: Catalog, name: string): HeuristicInfo | undefined {
  return catalog.heuristics.find((heuristic) => heuristic.name === name);
}

/** The draft for an algorithm with default capacities and FIFO everywhere. */
export function defaultDraft(algorithm: AlgorithmInfo, previous?: Partial<Draft>): Draft {
  return {
    presetKey: null,
    algorithm: algorithm.key,
    params: { ...algorithm.default_params },
    buffers: Object.fromEntries(
      algorithm.buffers.map((buffer) => [
        buffer.name,
        { capacity: buffer.default_capacity, heuristic: { name: "fifo", params: {} } },
      ]),
    ),
    stream: algorithm.stream,
    speed: previous?.speed ?? 200,
    trackBuffers: previous?.trackBuffers ?? true,
  };
}

export function presetDraft(catalog: Catalog, preset: Preset, previous?: Partial<Draft>): Draft | null {
  const algorithm = findAlgorithm(catalog, preset.algorithm);
  if (!algorithm) return null;
  const base = defaultDraft(algorithm, previous);
  return {
    ...base,
    presetKey: preset.key,
    params: { ...base.params, ...preset.params },
    buffers: { ...base.buffers, ...structuredClone(preset.buffers) },
  };
}

/** The parameters of a heuristic, completed with its defaults. */
export function heuristicParams(info: HeuristicInfo | undefined, params: Record<string, unknown> | undefined) {
  return { ...(info?.default_params ?? {}), ...(params ?? {}) };
}

/**
 * The memory of a buffer in entries: its capacity plus the capacities of the private buffers of
 * its heuristic, recursively (paper: the sum of all capacities).
 */
export function bufferMemory(catalog: Catalog, capacity: number, heuristicName: string, params?: Record<string, unknown>): number {
  const info = findHeuristic(catalog, heuristicName);
  if (!info) return capacity;
  const values = heuristicParams(info, params);
  let total = capacity;
  for (const privateBuffer of info.private_buffers) {
    const privateCapacity = privateBuffer.capacity === "c" ? capacity : Number(values[privateBuffer.capacity] ?? 0);
    total += privateBuffer.heuristic
      ? bufferMemory(catalog, privateCapacity, privateBuffer.heuristic)
      : privateCapacity;
  }
  return total;
}

export function draftMemory(catalog: Catalog, draft: Draft): number {
  return Object.values(draft.buffers).reduce(
    (sum, buffer) => sum + bufferMemory(catalog, buffer.capacity, buffer.heuristic?.name ?? "fifo", buffer.heuristic?.params),
    0,
  );
}

export function toReplayConfig(draft: Draft, ocelId: string, name?: string): ReplayConfig {
  return {
    ocel_id: ocelId,
    algorithm: draft.algorithm,
    name,
    params: draft.params,
    buffers: draft.buffers,
    stream: draft.stream,
    speed: draft.speed,
    track_buffers: draft.trackBuffers,
  };
}

export function formatCount(value: number): string {
  return new Intl.NumberFormat("en-US").format(Math.round(value));
}
