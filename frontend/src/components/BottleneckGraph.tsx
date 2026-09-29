import { Background, Controls, Handle, Position, ReactFlow, type Node, type NodeProps } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { useMemo, useState } from 'react'
import { api } from '../api/client'
import type { DelayResponse, GraphNode, PlanRequest, PlanResponse, WhatIfResponse } from '../api/types'
import { formatTerms } from '../format'
import { layoutGraph, NODE_W, type CourseNodeData } from './graphLayout'
import { CriticalIcon, ErrorBox, Spinner } from './ui'


function CourseNode({ data, selected }: NodeProps<Node<CourseNodeData>>) {
  const node = data.node
  return (
    <div
      className={`rounded-lg border-2 bg-surface px-2.5 py-1.5 text-left shadow-sm ${
        node.critical ? 'border-critical' : 'border-line-strong'
      } ${selected ? 'ring-2 ring-ink' : ''}`}
      style={{ width: NODE_W }}
    >
      <Handle type="target" position={Position.Left} className="!h-2 !w-2 !border-0 !bg-line-strong" />
      <div className="flex items-center gap-1 text-[0.78rem] font-semibold">
        {node.critical && <CriticalIcon className="text-critical" />}
        <span className="truncate">{node.label}</span>
      </div>
      <div className="mt-0.5 flex items-center justify-between text-[0.68rem] text-muted">
        <span>{node.term}</span>
        <span title="Offered">{node.pattern || '—'}</span>
      </div>
      <div className={`text-[0.68rem] font-semibold ${node.critical ? 'text-critical' : 'text-saved'}`}>
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
  const chain = plan.critical_path
    .map((id) => plan.graph_nodes.find((n) => n.id === id))
    .filter((n): n is GraphNode => Boolean(n))

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="max-w-3xl text-sm text-ink-soft">
          Remaining courses laid out by term. <span className="font-semibold text-critical">◆ Critical</span> courses have zero{' '}
          <em>prerequisite slack</em> (it ignores hour caps): delaying one delays graduation. Click a course to test it with a true
          re-solve.
        </p>
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={showIsolated} onChange={(e) => setShowIsolated(e.target.checked)} />
          Show courses with no prerequisite links
        </label>
      </div>
      {chain.length > 0 && (
        <p className="rounded-lg border border-critical/40 bg-critical-soft px-3 py-2 text-sm text-critical">
          <CriticalIcon /> <strong>Critical chain:</strong> {chain.map((n) => `${n.label} (${n.term}, ${n.pattern || '—'})`).join(' → ')}
        </p>
      )}
      <div className="grid gap-4 lg:grid-cols-[1fr_20rem]">
        <div className="h-[32rem] overflow-hidden rounded-xl border border-line bg-paper" aria-label="Prerequisite graph">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={nodeTypes}
            fitView
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
              {n.critical ? '◆ ' : ''}
              {n.label} ({n.term})
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
            <p className={`rounded-md p-2 ${delay.terms_later && delay.terms_later > 0 ? 'bg-critical-soft text-critical' : 'bg-saved-soft text-saved'}`}>
              {delay.explanation}
            </p>
          )}
          {fail && fail.event.code === code && (
            <p className={`rounded-md p-2 ${fail.terms_later && fail.terms_later > 0 ? 'bg-critical-soft text-critical' : 'bg-saved-soft text-saved'}`}>
              {fail.explanation}
            </p>
          )}
        </div>
      )}
    </aside>
  )
}
