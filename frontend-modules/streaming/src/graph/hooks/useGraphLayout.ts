import { applyNodeChanges, type NodeChange } from "@xyflow/react";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { selectEngine } from "../layout/engine";
import { buildGraphModel } from "../model/buildModel";
import {
  type GraphError,
  type GraphModel,
  type GraphVisualization,
  type RenderEdge,
  type RenderNode,
  toGraphError,
} from "../model/types";
import { projectToRenderModel } from "../render/project";

// The whole pipeline in one place, as a straight line:
//
//   visualization → build model + select engine  (sync, memoized)
//                 → run engine                    (async black box)
//                 → project to render model       (sync)
//                 → nodes + edges                 (state)
//
// Each arrow is a single function from another module; this hook only sequences
// them and owns the resulting React state. Because edge paths are computed here
// (absolute, from layout geometry), nothing waits on React Flow to measure the
// DOM — the canvas simply stays hidden until `ready`.
type Prepared =
  | { model: GraphModel; engine: ReturnType<typeof selectEngine>; error: null }
  | { model: null; engine: null; error: GraphError };

const prepare = (visualization: GraphVisualization): Prepared => {
  try {
    return {
      model: buildGraphModel(visualization),
      engine: selectEngine(visualization),
      error: null,
    };
  } catch (err) {
    return { model: null, engine: null, error: toGraphError(err) };
  }
};

export const useGraphLayout = (visualization: GraphVisualization) => {
  const {
    model,
    engine,
    error: prepareError,
  } = useMemo(() => prepare(visualization), [visualization]);

  const [nodes, setNodes] = useState<RenderNode[]>([]);
  const [edges, setEdges] = useState<RenderEdge[]>([]);
  const [ready, setReady] = useState(false);
  const [runError, setRunError] = useState<GraphError | null>(null);

  // Streaming change: the previous layout stays on screen while the next one is
  // computed, and only the newest model is laid out once the running layout is
  // done (models arriving in between are skipped). So `ready` turns false only
  // before the very first layout.
  type Job = { model: GraphModel; engine: NonNullable<Prepared["engine"]> };
  const pending = useRef<Job | null>(null);
  const running = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  const runNext = useCallback(() => {
    const job = pending.current;
    pending.current = null;
    running.current = job !== null;
    if (!job) return;
    job.engine.run(job.model).then(
      (result) => {
        if (!mounted.current) return;
        const projected = projectToRenderModel(job.model, result);
        setNodes(projected.nodes);
        setEdges(projected.edges);
        setReady(true);
        runNext();
      },
      (err) => {
        if (!mounted.current) return;
        setRunError(toGraphError(err));
        setReady(true);
        runNext();
      },
    );
  }, []);

  useEffect(() => {
    setRunError(null);

    if (!model || !engine || model.nodes.length === 0) {
      pending.current = null;
      setNodes([]);
      setEdges([]);
      setReady(true);
      return;
    }

    pending.current = { model, engine };
    if (!running.current) runNext();
  }, [model, engine, runNext]);

  // Keep React Flow's measurement-driven node updates flowing (sizes, etc.)
  // without letting the user move nodes.
  const onNodesChange = useCallback(
    (changes: NodeChange<RenderNode>[]) =>
      setNodes((current) => applyNodeChanges(changes, current)),
    [],
  );

  return {
    nodes,
    edges,
    ready,
    error: prepareError ?? runError,
    onNodesChange,
  };
};
