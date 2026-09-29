import dagre from '@dagrejs/dagre'
import { MarkerType, type Edge, type Node } from '@xyflow/react'
import type { GraphNode, PlanResponse } from '../api/types'

export const NODE_W = 176
export const NODE_H = 64
export const COLUMN_GAP = 64

export type CourseNodeData = { node: GraphNode }

export function layoutGraph(plan: PlanResponse, showIsolated: boolean): { nodes: Node<CourseNodeData>[]; edges: Edge[] } {
  const linked = new Set<string>()
  plan.graph_edges.forEach((e) => {
    linked.add(e.source)
    linked.add(e.target)
  })
  const nodes = plan.graph_nodes.filter((n) => showIsolated || linked.has(n.id) || n.critical)
  const ids = new Set(nodes.map((n) => n.id))
  const columns = [...new Set(nodes.map((n) => n.term_index))].sort((a, b) => a - b)
  const graph = new dagre.graphlib.Graph()
  graph.setGraph({ rankdir: 'LR', nodesep: 14, ranksep: COLUMN_GAP })
  graph.setDefaultEdgeLabel(() => ({}))
  nodes.forEach((n) => graph.setNode(n.id, { width: NODE_W, height: NODE_H }))
  plan.graph_edges.forEach((e) => {
    if (ids.has(e.source) && ids.has(e.target)) graph.setEdge(e.source, e.target)
  })
  dagre.layout(graph)
  // Pin x to the term column so the graph reads left to right by term (PRD F5).
  const perColumn = new Map<number, { id: string; y: number }[]>()
  nodes.forEach((n) => {
    const pos = graph.node(n.id)
    const list = perColumn.get(n.term_index) ?? []
    list.push({ id: n.id, y: pos?.y ?? 0 })
    perColumn.set(n.term_index, list)
  })
  const y = new Map<string, number>()
  perColumn.forEach((list) => {
    list.sort((a, b) => a.y - b.y)
    list.forEach((item, i) => y.set(item.id, i * (NODE_H + 18)))
  })
  return {
    nodes: nodes.map((n) => ({
      id: n.id,
      type: 'course',
      position: { x: columns.indexOf(n.term_index) * (NODE_W + COLUMN_GAP), y: y.get(n.id) ?? 0 },
      data: { node: n },
    })),
    edges: plan.graph_edges
      .filter((e) => ids.has(e.source) && ids.has(e.target))
      .map((e) => ({
        id: `${e.source}->${e.target}`,
        source: e.source,
        target: e.target,
        animated: e.critical,
        style: {
          stroke: e.critical ? '#000000' : '#bdbdbd',
          strokeWidth: e.critical ? 2.4 : 1.4,
          strokeDasharray: e.kind === 'coreq' ? '4 3' : undefined,
        },
        markerEnd: { type: MarkerType.ArrowClosed, color: e.critical ? '#000000' : '#bdbdbd' },
      })),
  }
}
