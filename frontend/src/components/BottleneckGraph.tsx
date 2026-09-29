import {
  Background,
  Controls,
  Handle,
  Position,
  ReactFlow,
  type Node,
  type NodeProps,
  type ReactFlowInstance,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useCallback, useMemo, useRef, useState } from 'react'
import { api } from '../api/client'
import type { DelayResponse, GraphNode, PlanRequest, PlanResponse, WhatIfResponse } from '../api/types'
import { formatTerms } from '../format'
import { layoutGraph, NODE_H, NODE_W, type CourseNodeData } from './graphLayout'
import { ErrorBox, Spinner } from './ui'


function CourseNode({ data, selected }: NodeProps<Node<CourseNodeData>>) {
  const node = data.node
  return (
    <div
      className={`rounded-md bg-surface px-2.5 py-1.5 text-left ${
        node.critical ? 'border-2 border-ink' : 'border border-line-strong'
      } ${selected ? 'outline outline-2 outline-ink' : ''}`}
      style={{ width: NODE_W }}
    >
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-0 !bg-line-strong" />
      <div className="truncate text-[0.78rem] font-semibold">{node.label}</div>
      <div className="mt-0.5 flex items-center justify-between text-[0.68rem] text-muted">
        <span>{node.term}</span>
        <span title="Offered">{node.pattern || '—'}</span>
      </div>
      <div className={`text-[0.68rem] ${node.critical ? 'font-semibold text-ink' : 'text-muted'}`}>
        {node.critical ? 'Critical · 0 slack' : `Slack ${formatTerms(node.slack)}`}
      </div>
      <Handle type="source" position={Position.Right} className="!h-2 !w-2 !border-0 !bg-line-strong" />
    </div>
  )
}

const nodeTypes = { course: CourseNode }

export function BottleneckGraph({
  plan,
  request,
}: {
  plan: PlanResponse
  request: PlanRequest
}) {
  const [showIsolated, setShowIsolated] = useState(false)
  const [selected, setSelected] = useState<GraphNode | null>(null)
  const { nodes, edges } = useMemo(() => layoutGraph(plan, showIsolated), [plan, showIsolated])
  const byId = useMemo(() => new Map(plan.graph_nodes.map((n) => [n.id, n])), [plan])
  const chainIds = plan.critical_chain?.length ? plan.critical_chain : plan.critical_path
  const chain = chainIds.map((id) => byId.get(id)).filter((n): n is GraphNode => Boolean(n))
  const alsoCritical = plan.critical_path
    .filter((id) => !chainIds.includes(id))
    .map((id) => byId.get(id)?.label)
    .filter(Boolean)
  const wrapper = useRef<HTMLDivElement>(null)
  // Open at the first term (not centred): the chain reads left to right from where it starts.
  const openAtStart = useCallback(
    (instance: ReactFlowInstance<Node<CourseNodeData>>) => {
      if (nodes.length === 0) return
      const width = wrapper.current?.clientWidth ?? 900
      const height = wrapper.current?.clientHeight ?? 512
      const graphW = Math.max(...nodes.map((n) => n.position.x)) + NODE_W
      const graphH = Math.max(...nodes.map((n) => n.position.y)) + NODE_H
      const zoom = Math.min(1.1, Math.max(0.6, Math.min((width - 32) / graphW, (height - 32) / graphH)))
      void instance.setViewport({ x: 16, y: Math.max(16, (height - graphH * zoom) / 2), zoom })
    },
    [nodes],
  )

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-3xl text-sm text-ink-soft">
          Remaining courses laid out by term. <strong>Critical</strong> courses (bold border) have zero{' '}
          <em>prerequisite slack</em> (it ignores hour caps): delaying one delays graduation. Click a course to test it with a true
          re-solve.
        </p>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={showIsolated} onChange={(e) => setShowIsolated(e.target.checked)} />
          Show courses with no prerequisite links
        </label>
      </div>
      {chain.length > 0 && (
        <p className="rounded-md border border-ink px-3 py-2 text-sm">
          <strong>Critical chain:</strong> {chain.map((n) => `${n.label} (${n.term}, ${n.pattern || '—'})`).join(' → ')}
          {alsoCritical.length > 0 && (
            <span className="mt-1 block text-ink-soft">Also zero slack: {alsoCritical.join(', ')}</span>
          )}
        </p>
      )}
      <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
        <div ref={wrapper} className="h-[32rem] overflow-hidden rounded-md border border-line bg-paper" aria-label="Prerequisite graph">
          <ReactFlow
            key={String(showIsolated)}
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            onInit={openAtStart}
            minZoom={0.25}
            nodesDraggable={false}
            nodesConnectable={false}
            onNodeClick={(_, node) => setSelected((node.data as CourseNodeData).node)}
            proOptions={{ hideAttribution: true }}
          >
            <Background gap={24} color="#e2dcd1" />
            <Controls showInteractive={false} />
          </ReactFlow>
        </div>
        <CourseActions node={selected} request={request} nodes={plan.graph_nodes} onPick={setSelected} />
      </div>
    </div>
  )
}

function CourseActions({
  node,
  request,
  nodes,
  onPick,
}: {
  node: GraphNode | null
  request: PlanRequest
  nodes: GraphNode[]
  onPick: (node: GraphNode) => void
}) {
  const [busy, setBusy] = useState<'delay' | 'fail' | null>(null)
  const [delay, setDelay] = useState<DelayResponse | null>(null)
  const [fail, setFail] = useState<WhatIfResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const code = node?.label ?? ''
  const isCourse = Boolean(node && /^[A-Z]{2,5} \d{4}$/.test(node.label))

  const run = async (kind: 'delay' | 'fail') => {
    if (!node) return
    setBusy(kind)
    setError(null)
    try {
      if (kind === 'delay') setDelay(await api.delayImpact(request, node.id))
      else setFail(await api.whatIf(request, { type: 'fail', code: node.label }))
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err))
    } finally {
      setBusy(null)
    }
  }

  return (
    <aside className="card p-4" aria-live="polite">
      <label className="block text-sm">
        <span className="font-semibold">Course</span>
        <select
          className="input mt-1"
          value={node?.id ?? ''}
          onChange={(e) => {
            const pick = nodes.find((n) => n.id === e.target.value)
            if (pick) {
              onPick(pick)
              setDelay(null)
              setFail(null)
            }
          }}
        >
          <option value="">Pick a course…</option>
          {nodes.map((n) => (
            <option key={n.id} value={n.id}>
              {n.label} ({n.term}){n.critical ? ' · critical' : ''}
            </option>
          ))}
        </select>
      </label>
      {node && (
        <div className="mt-3 space-y-3 text-sm">
          <p>
            <strong>{node.label}</strong> {node.title !== node.label && <span className="text-ink-soft">{node.title}</span>}
            <br />
            <span className="text-muted">
              {node.term} · offered {node.pattern || '—'} · {node.critical ? 'critical' : `slack ${formatTerms(node.slack)}`}
            </span>
          </p>
          <div className="flex flex-wrap gap-2">
            <button type="button" className="btn-secondary" disabled={busy !== null} onClick={() => void run('delay')}>
              What if I delay this one term?
            </button>
            {isCourse && (
              <button type="button" className="btn-secondary" disabled={busy !== null} onClick={() => void run('fail')}>
                What if I fail it?
              </button>
            )}
          </div>
          {busy && <Spinner label="Re-solving…" />}
          {error && <ErrorBox message={error} />}
          {delay && delay.item_id === node.id && (
            <p className={`rounded-md p-2 ${delay.terms_later && delay.terms_later > 0 ? 'border border-ink font-medium' : 'border border-line'}`}>
              {delay.explanation}
            </p>
          )}
          {fail && fail.event.code === code && (
            <p className={`rounded-md p-2 ${fail.terms_later && fail.terms_later > 0 ? 'border border-ink font-medium' : 'border border-line'}`}>
              {fail.explanation}
            </p>
          )}
        </div>
      )}
    </aside>
  )
}
