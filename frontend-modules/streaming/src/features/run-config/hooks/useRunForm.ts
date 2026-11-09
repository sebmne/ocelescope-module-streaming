import { useMemo, useReducer } from "react";
import type { Catalog } from "../../../api/streaming";
import { initialRunForm, runFormReducer, sortAlgorithms, validateRunForm } from "../model";

/**
 * Form state of a new run. Starts with the first algorithm in display order, all buffers unbounded.
 * The catalog must contain at least one algorithm.
 */
export function useRunForm(catalog: Catalog) {
  const [state, dispatch] = useReducer(runFormReducer, sortAlgorithms(catalog.algorithms)[0], initialRunForm);
  const algorithm = catalog.algorithms.find((candidate) => candidate.key === state.algorithm);
  const errors = useMemo(() => validateRunForm(state, catalog.heuristics), [state, catalog.heuristics]);
  return { state, dispatch, algorithm, errors };
}
