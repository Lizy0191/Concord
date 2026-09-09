import { useMemo } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
  type Node,
  type Edge,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { Workspace } from "../api/client";

export default function ImpactGraph({
  workspace,
  selected,
  onConstraint,
}: {
  workspace: Workspace;
  selected: string;
  onConstraint: (id: string) => void;
}) {
  const { nodes, edges } = useMemo(() => {
    const wp = workspace.state.work_packages.find((p) => p.id === selected)!;
    const constraints = (workspace.analysis?.constraints ?? [])
      .filter((c) => c.work_package_id === selected)
      .slice(0, 8);
    const proposal = workspace.proposals.find(
      (p) => p.work_package_id === selected,
    );
    const nodes: Node[] = [
      {
        id: "source",
        position: { x: 30, y: 80 },
        className: "graph-node source-node",
        data: {
          label: (
            <>
              <small>SOURCE / DRAWING</small>
              <strong>{wp.design_revision ?? "V16"}</strong>
              <span>Revision-bound project facts</span>
            </>
          ),
        },
      },
      {
        id: wp.id,
        position: { x: 340, y: 80 },
        className: `graph-node ${constraints.length ? "node-blocked" : "node-ready"}`,
        data: {
          label: (
            <>
              <small>
                {wp.id} / {wp.discipline}
              </small>
              <strong>{wp.name}</strong>
              <span>
                {constraints.length
                  ? `${constraints.length} blocking constraints`
                  : "No unresolved constraints"}
              </span>
            </>
          ),
        },
      },
    ];
    const edges: Edge[] = [
      {
        id: "source-package",
        source: "source",
        target: wp.id,
        label: "governs",
        markerEnd: { type: MarkerType.ArrowClosed },
      },
    ];
    constraints.forEach((c, index) => {
      nodes.push({
        id: c.id,
        position: { x: 330, y: 260 + index * 150 },
        className: "graph-node constraint-node",
        data: {
          label: (
            <>
              <small>CONSTRAINT / {c.kind}</small>
              <strong>{c.description}</strong>
              <span>{c.evidence_ids.length} persisted evidence reference</span>
            </>
          ),
        },
      });
      edges.push({
        id: `edge-${c.id}`,
        source: c.id,
        target: wp.id,
        label: "blocks",
        markerEnd: { type: MarkerType.ArrowClosed },
      });
    });
    if (proposal) {
      nodes.push({
        id: proposal.id ?? "proposal",
        position: { x: 660, y: 80 },
        className: "graph-node action-node",
        data: {
          label: (
            <>
              <small>PROPOSAL / R{proposal.risk}</small>
              <strong>Coordinate & re-check</strong>
              <span>Human approval required</span>
            </>
          ),
        },
      });
      edges.push({
        id: "package-proposal",
        source: wp.id,
        target: proposal.id ?? "proposal",
        label: "resolve",
        markerEnd: { type: MarkerType.ArrowClosed },
      });
    }
    for (const [index, predecessor] of (wp.predecessors ?? []).entries()) {
      nodes.push({
        id: predecessor,
        position: { x: 30, y: 280 + index * 150 },
        className: "graph-node",
        data: {
          label: (
            <>
              <small>PREDECESSOR</small>
              <strong>{predecessor}</strong>
              <span>Schedule dependency</span>
            </>
          ),
        },
      });
      edges.push({
        id: `pred-${predecessor}`,
        source: predecessor,
        target: wp.id,
        label: "precedes",
      });
    }
    return { nodes, edges };
  }, [workspace, selected]);
  return (
    <div className="graph-canvas" aria-label="Impact graph">
      <div className="canvas-label">
        <span className="eyebrow">DEPENDENCY LENS</span>
        <span>Relevant workface subgraph</span>
      </div>
      <ReactFlow
        key={`${selected}-${workspace.analysis?.id}`}
        nodes={nodes}
        edges={edges}
        fitView
        fitViewOptions={{ padding: 0.3 }}
        minZoom={0.35}
        maxZoom={1.4}
        nodesDraggable={false}
        nodesConnectable={false}
        onNodeClick={(_, node) => onConstraint(node.id)}
        proOptions={{ hideAttribution: false }}
      >
        <Background gap={24} size={1} />
        <Controls showInteractive={false} />
      </ReactFlow>
    </div>
  );
}
