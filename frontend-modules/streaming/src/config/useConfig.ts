import { useState } from "react";
import type { AlgorithmInfo, RunConfig } from "../api/streaming";

export type Kind = AlgorithmInfo["kinds"][number];
export type Params = Record<string, unknown>;
export type BufferState = { bounded: boolean; capacity: number; heuristic: string; params: Params };
export type ConfigState = {
  algorithm: AlgorithmInfo;
  kinds: Kind[];
  buffers: Record<string, BufferState>;
  name: string;
};

const DEFAULT_CAPACITY = 1000;

function initial(algorithm: AlgorithmInfo, heuristic: string): ConfigState {
  const buffer = { bounded: false, capacity: DEFAULT_CAPACITY, heuristic, params: {} };
  return {
    algorithm,
    kinds: algorithm.kinds,
    buffers: Object.fromEntries(algorithm.buffers.map((name) => [name, buffer])),
    name: "",
  };
}

/** Form state of a new run, starting with `algorithms[0]` and all buffers unbounded. */
export function useConfig(algorithms: AlgorithmInfo[], defaultHeuristic: string) {
  const [config, setConfig] = useState(() => initial(algorithms[0], defaultHeuristic));

  return {
    config,
    selectAlgorithm: (key: string) => {
      const algorithm = algorithms.find((candidate) => candidate.key === key);
      if (algorithm) setConfig((current) => ({ ...initial(algorithm, defaultHeuristic), name: current.name }));
    },
    setKinds: (kinds: Kind[]) => setConfig((current) => ({ ...current, kinds })),
    setBuffer: (name: string, patch: Partial<BufferState>) =>
      setConfig((current) => ({
        ...current,
        buffers: { ...current.buffers, [name]: { ...current.buffers[name], ...patch } },
      })),
    setName: (name: string) => setConfig((current) => ({ ...current, name })),
  };
}

export function toRunConfig(config: ConfigState, ocelId: string): RunConfig {
  return {
    ocel_id: ocelId,
    algorithm: config.algorithm.key,
    kinds: config.kinds,
    name: config.name.trim() || null,
    buffers: Object.fromEntries(
      Object.entries(config.buffers)
        .filter(([, buffer]) => buffer.bounded)
        .map(([name, buffer]) => [name, { capacity: buffer.capacity, heuristic: buffer.heuristic, params: buffer.params }]),
    ),
  };
}
