import { Alert, Code, LoadingOverlay, Stack } from "@mantine/core";
import {
  Background,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from "@xyflow/react";
import { useCallback, useEffect, useMemo, useRef } from "react";
import type { VisualizationProps } from "./types";
import GraphControls from "./GraphControls";
import { useGraphExport } from "./hooks/useGraphExport";
import { useGraphLayout } from "./hooks/useGraphLayout";
import { FIT_VIEW_PADDING, type GraphVisualization } from "./model/types";
import GraphFlowEdge from "./render/Edge";
import GraphFlowNode from "./render/Node";
import { pinToFrame } from "./render/pin";
import { computeAutoFitBounds } from "./utils/bounds";

const nodeTypes = { node: GraphFlowNode };
const edgeTypes = { graphflow: GraphFlowEdge };

// Streaming change: with a `layout` (the union of all frames of a run), the union
// is laid out once and each `visualization` frame only decides what is shown.
type GraphFlowProps = VisualizationProps<"graph"> & {
  layout?: GraphVisualization | undefined;
};

const GraphFlowCanvas = ({
  visualization,
  layout,
  isPreview,
  menuItems,
}: GraphFlowProps) => {
  const {
    nodes: laidOutNodes,
    edges: laidOutEdges,
    ready,
    error,
    onNodesChange,
  } = useGraphLayout(layout ?? visualization);
  const { nodes, edges } = useMemo(
    () =>
      layout
        ? pinToFrame(laidOutNodes, laidOutEdges, visualization)
        : { nodes: laidOutNodes, edges: laidOutEdges },
    [layout, laidOutNodes, laidOutEdges, visualization],
  );

  const { fitBounds } = useReactFlow();
  const wrapperRef = useRef<HTMLDivElement>(null);
  const { downloadPng, downloadSvg, downloadPdf } = useGraphExport(wrapperRef);

  // Streaming change: fits everything laid out, so with a fixed layout the
  // view covers the whole run from the start.
  const fitViewWithEdges = useCallback(() => {
    fitBounds(computeAutoFitBounds(laidOutNodes, laidOutEdges), {
      padding: FIT_VIEW_PADDING,
    });
  }, [fitBounds, laidOutNodes, laidOutEdges]);

  // Streaming change: the view follows the growing graph after every layout
  // until the user zooms or pans; the fit button makes it follow again.
  const followRef = useRef(true);
  useEffect(() => {
    if (ready && followRef.current && laidOutNodes.length > 0) fitViewWithEdges();
  }, [ready, laidOutNodes, fitViewWithEdges]);
  const follow = useCallback(() => {
    followRef.current = true;
    fitViewWithEdges();
  }, [fitViewWithEdges]);

  if (error) {
    return (
      <Stack h="100%" justify="center" p="md">
        <Alert color="red" title={error.message}>
          {error.details?.map((detail) => (
            <Code key={detail} display="block" mb={4}>
              {detail}
            </Code>
          ))}
        </Alert>
      </Stack>
    );
  }

  return (
    <>
      <LoadingOverlay visible={!ready} zIndex={10} />
      <div
        ref={wrapperRef}
        style={{ width: "100%", height: "100%", opacity: ready ? 1 : 0 }}
      >
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          onNodesChange={onNodesChange}
          nodesDraggable={false}
          nodesConnectable={false}
          elementsSelectable={false}
          zoomOnScroll={!isPreview}
          panOnDrag={!isPreview}
          minZoom={0.05}
          maxZoom={3}
          onMoveStart={(event) => {
            if (event) followRef.current = false; // only user moves carry an event
          }}
        >
          {!isPreview && <Background color="#e5e7eb" gap={20} size={1} />}
          <GraphControls
            isPreview={isPreview}
            onFitView={follow}
            onDownloadPng={downloadPng}
            onDownloadSvg={downloadSvg}
            onDownloadPdf={downloadPdf}
            menuItems={menuItems}
          />
        </ReactFlow>
      </div>
    </>
  );
};

const GraphFlow = (props: GraphFlowProps) => (
  <ReactFlowProvider>
    <GraphFlowCanvas {...props} />
  </ReactFlowProvider>
);

export default GraphFlow;
