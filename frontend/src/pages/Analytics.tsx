import { useQuery } from '@tanstack/react-query'
import { BarChart3, ShieldCheck } from 'lucide-react'
import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis } from 'recharts'
import { useNow } from '@/components/Shell'
import { Button, EmptyState, Panel, PanelHeader, Segmented, Skeleton, StatusDot } from '@/components/ui'
import { api, type Analytics as Data } from '@/lib/api'
import { clock, FAMILIES, relTime } from '@/lib/utils'

// Nine incident types are grouped into five families so the chart stays readable. Family
// colours were checked with the dataviz palette validator against the dark surface, in
// this order; severity colours (red / orange / amber) are never used for series.
const SERIES = FAMILIES
const NEUTRAL = '#5d6878'
const AXIS = { fontSize: 11, fill: '#5d6878', fontFamily: 'JetBrains Mono Variable, monospace' }

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <Panel className="px-3 py-2.5">
      <div className="text-[11px] uppercase tracking-wider text-faint">{label}</div>
      <div className="num mt-1 text-[22px] font-semibold leading-none text-fg">{value}</div>
      {sub && <div className="mt-1.5 text-[12px] text-muted">{sub}</div>}
    </Panel>
  )
}

function Legend({ items }: { items: { label: string; color: string }[] }) {
  return (
    <div className="flex items-center gap-3">
      {items.map((i) => (
        <span key={i.label} className="flex items-center gap-1.5 text-[12px] text-muted">
          <span className="h-2 w-2 rounded-[2px]" style={{ background: i.color }} />
          {i.label}
        </span>
      ))}
    </div>
  )
}

function Tip({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: number }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-md border border-line-strong bg-raised px-2.5 py-2 text-[12px] shadow-lg shadow-black/40">
      <div className="num mb-1 text-faint">{label ? clock(label) : ''}</div>
      {payload.map((p) => (
        <div key={p.name} className="flex items-center justify-between gap-4">
          <span className="flex items-center gap-1.5 text-muted"><span className="h-2 w-2 rounded-[2px]" style={{ background: p.color }} />{p.name}</span>
          <span className="num text-fg">{Number.isInteger(p.value) ? p.value : p.value.toFixed(1)}</span>
        </div>
      ))}
    </div>
  )
}

function HBar({ rows, total }: { rows: [string, number][]; total: number }) {
  return (
    <ul className="space-y-2.5 p-3">
      {rows.map(([k, v]) => (
        <li key={k}>
          <div className="mb-1 flex items-baseline justify-between text-[12px]">
            <span className="capitalize text-muted">{k}</span>
            <span className="num text-fg">{v}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-raised">
            <div className="h-full rounded-full" style={{ width: `${total ? (v / total) * 100 : 0}%`, background: NEUTRAL }} />
          </div>
        </li>
      ))}
    </ul>
  )
}

function CameraFps({ data }: { data: Data }) {
  return (
    <table className="w-full text-left text-[12px]">
      <thead>
        <tr className="border-b border-line text-[11px] uppercase tracking-wider text-faint">
          <th className="h-8 px-3 font-medium">Camera</th>
          <th className="px-3 font-medium">Trend</th>
          <th className="px-3 text-right font-medium">FPS</th>
          <th className="px-3 text-right font-medium">Latency</th>
        </tr>
      </thead>
      <tbody>
        {data.cameras.map((c) => {
          const pts = data.fps.filter((f) => f.camera_id === c.id)
          return (
            <tr key={c.id} className="border-b border-line last:border-0">
              <td className="h-11 px-3"><span className="flex items-center gap-2 text-[13px] text-fg"><StatusDot status={c.status} />{c.name}</span></td>
              <td className="w-[46%] px-3">
                {pts.length > 1 ? (
                  <div className="h-7">
                    <ResponsiveContainer width="100%" height="100%">
                      <LineChart data={pts} margin={{ top: 3, bottom: 3, left: 0, right: 0 }}>
                        <YAxis hide domain={[0, 'dataMax + 2']} />
                        <XAxis dataKey="ts" hide />
                        <ChartTooltip content={<Tip />} cursor={{ stroke: '#2a3442' }} />
                        <Line type="monotone" dataKey="fps" name="FPS" stroke="#3987e5" strokeWidth={2} dot={false} isAnimationActive={false} />
                      </LineChart>
                    </ResponsiveContainer>
                  </div>
                ) : (
                  <span className="text-faint">Collecting samples (one every 10 s)</span>
                )}
              </td>
              <td className="num px-3 text-right text-fg">{c.status === 'online' ? c.fps.toFixed(1) : '0.0'}</td>
              <td className="num px-3 text-right text-muted">{c.status === 'online' ? `${c.latency_ms} ms` : 'n/a'}</td>
            </tr>
          )
        })}
      </tbody>
    </table>
  )
}

export function Analytics() {
  const now = useNow()
  const [minutes, setMinutes] = useState<'30' | '60' | '360'>('30')
  const q = useQuery({ queryKey: ['analytics', minutes], queryFn: () => api.analytics(Number(minutes)), refetchInterval: 10_000 })
  const d = q.data

  if (q.isLoading) {
    return (
      <div className="space-y-3 p-3">
        <div className="grid grid-cols-4 gap-3">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-[76px] rounded-lg" />)}</div>
        <Skeleton className="h-64 rounded-lg" />
      </div>
    )
  }
  if (!d) {
    return <EmptyState icon={BarChart3} title="Could not load analytics" action={<Button size="sm" onClick={() => q.refetch()}>Retry</Button>}>The backend did not answer.</EmptyState>
  }

  const raised = d.incidents + d.suppressed
  const online = d.cameras.filter((c) => c.status === 'online')
  const fpsAvg = online.length ? online.reduce((s, c) => s + c.fps, 0) / online.length : 0
  const series = d.series.map((row) => ({
    t: row.t,
    ...Object.fromEntries(SERIES.map((f) => [f.key, f.types.reduce((n, t) => n + (row[t] ?? 0), 0)])),
  }))
  const byFamily = Object.fromEntries(SERIES.map((f) => [f.key, f.types.reduce((n, t) => n + (d.by_type[t] ?? 0), 0)]))
  const hasSeries = series.some((row) => SERIES.some((f) => (row as Record<string, number>)[f.key] > 0))
  const tick = (t: number) => clock(t).slice(0, 5)

  return (
    <div className="mx-auto max-w-[1500px] space-y-3 p-3">
      <div className="flex items-center justify-between">
        <p className="text-[12px] text-muted">Counts come from the incident and suppression logs in SQLite. Nothing here is estimated.</p>
        <Segmented value={minutes} onChange={setMinutes} options={[{ value: '30', label: '30 min' }, { value: '60', label: '1 h' }, { value: '360', label: '6 h' }]} />
      </div>

      <div className="grid grid-cols-4 gap-3">
        <Tile label="Incidents raised" value={String(d.incidents)} sub={`${d.by_status.confirmed ?? 0} confirmed, ${d.by_status.dismissed ?? 0} dismissed`} />
        <Tile label="False alarms suppressed" value={String(d.suppressed)} sub={raised ? `${Math.round((d.suppressed / raised) * 100)}% of ${raised} raw detections` : 'No raw detections yet'} />
        <Tile label="Operator feedback" value={String((d.feedback.confirm ?? 0) + (d.feedback.dismiss ?? 0))} sub={d.thresholds.length ? `${d.thresholds.length} camera gate${d.thresholds.length > 1 ? 's' : ''} adjusted` : 'No gates adjusted'} />
        <Tile label="Average FPS" value={fpsAvg.toFixed(1)} sub={`${online.length} of ${d.cameras.length} cameras online`} />
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)_340px] gap-3">
        <Panel>
          <PanelHeader title="Incidents over time" meta={`per ${d.bucket_s / 60} min, by family`}><Legend items={SERIES.map((s) => ({ label: s.label, color: s.color }))} /></PanelHeader>
          {hasSeries ? (
            <div className="h-60 px-2 pb-2 pt-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={series} barCategoryGap={2}>
                  <CartesianGrid stroke="#1e2631" vertical={false} />
                  <XAxis dataKey="t" tickFormatter={tick} tick={AXIS} axisLine={{ stroke: '#1e2631' }} tickLine={false} minTickGap={40} />
                  <YAxis allowDecimals={false} tick={AXIS} axisLine={false} tickLine={false} width={28} />
                  <ChartTooltip content={<Tip />} cursor={{ fill: '#161c25' }} />
                  {SERIES.map((s, i) => (
                    <Bar key={s.key} dataKey={s.key} name={s.label} stackId="a" fill={s.color} stroke="#11161d" strokeWidth={1} radius={i === SERIES.length - 1 ? [3, 3, 0, 0] : 0} maxBarSize={18} isAnimationActive={false} />
                  ))}
                </BarChart>
              </ResponsiveContainer>
            </div>
          ) : (
            <EmptyState icon={BarChart3} title="No incidents in this window">Bars appear here as incidents are raised.</EmptyState>
          )}
        </Panel>
        <Panel>
          <PanelHeader title="By type" meta={String(d.incidents)} />
          {d.incidents ? (
            <ul className="space-y-2.5 p-3">
              {SERIES.map((s) => (
                <li key={s.key}>
                  <div className="mb-1 flex items-baseline justify-between text-[12px]">
                    <span className="flex items-center gap-1.5 text-muted"><span className="h-2 w-2 rounded-[2px]" style={{ background: s.color }} />{s.label}</span>
                    <span className="num text-fg">{byFamily[s.key] ?? 0}</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-raised">
                    <div className="h-full rounded-full" style={{ width: `${((byFamily[s.key] ?? 0) / d.incidents) * 100}%`, background: s.color }} />
                  </div>
                </li>
              ))}
            </ul>
          ) : (
            <p className="px-3 py-4 text-[12px] text-muted">No incidents yet.</p>
          )}
        </Panel>
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)_340px] gap-3">
        <Panel>
          <PanelHeader title="Suppressed false alarms" meta="Most recent, with the check that stopped each one" />
          {d.suppressed_recent.length ? (
            <table className="w-full text-left text-[12px]">
              <thead>
                <tr className="border-b border-line text-[11px] uppercase tracking-wider text-faint">
                  <th className="h-8 px-3 font-medium">When</th>
                  <th className="px-3 font-medium">Camera</th>
                  <th className="px-3 font-medium">Type</th>
                  <th className="px-3 font-medium">Why it was suppressed</th>
                  <th className="px-3 text-right font-medium">Peak conf.</th>
                </tr>
              </thead>
              <tbody>
                {d.suppressed_recent.map((r) => (
                  <tr key={r.id} className="border-b border-line last:border-0">
                    <td className="num h-9 whitespace-nowrap px-3 text-faint">{relTime(r.ts, now)}</td>
                    <td className="px-3 text-muted">{d.cameras.find((c) => c.id === r.camera_id)?.name ?? r.camera_id}</td>
                    <td className="px-3 capitalize text-muted">{r.type}</td>
                    <td className="px-3 text-fg">{r.reason}</td>
                    <td className="num px-3 text-right text-muted">{r.conf.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <EmptyState icon={ShieldCheck} title="Nothing suppressed yet">Detections that fail the persistence, confidence or zone checks are logged here instead of reaching the queue.</EmptyState>
          )}
        </Panel>
        <Panel>
          <PanelHeader title="Suppressed by check" meta={String(d.suppressed)} />
          {d.suppressed ? <HBar rows={Object.entries(d.suppressed_by_check).sort((a, b) => b[1] - a[1])} total={d.suppressed} /> : <p className="px-3 py-4 text-[12px] text-muted">No suppressions yet.</p>}
        </Panel>
      </div>

      <Panel>
        <PanelHeader title="Per-camera throughput" meta="Frames processed per second, end to end" />
        {d.cameras.length ? <CameraFps data={d} /> : <p className="px-3 py-4 text-[12px] text-muted">No cameras.</p>}
      </Panel>
    </div>
  )
}
