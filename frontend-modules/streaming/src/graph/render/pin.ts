import type { GraphVisualization, RenderEdge, RenderNode } from "../model/types";

// Streaming change: shows only the elements of `frame`, placed where the laid-out
// union of all frames put them. Labels and annotations come from the frame;
// positions, routes, sizes and colors stay those of the union, so nothing moves.
export const pinToFrame = (
  nodes: RenderNode[],
  edges: RenderEdge[],
  frame: GraphVisualization,
): { nodes: RenderNode[]; edges: RenderEdge[] } => {
  const frameNodes = new Map(frame.nodes?.map((node) => [node.id, node]));
  const frameEdges = new Map(frame.edges?.map((edge) => [edge.id, edge]));
  return {
    nodes: nodes.flatMap((node) => {
      const current = frameNodes.get(node.id);
      if (!current) return [];
      const model = { ...node.data.model, label: current.label, annotation: current.annotation };
      return [{ ...node, data: { ...node.data, model } }];
    }),
    edges: edges.flatMap((edge) => {
      const current = edge.data && frameEdges.get(edge.id);
      if (!edge.data || !current) return [];
      const model = { ...edge.data.model, label: current.label, annotation: current.annotation };
      return [{ ...edge, data: { ...edge.data, model } }];
    }),
  };
};
