import { useQuery } from '@tanstack/react-query'
import { ArrowLeft, Check, FileQuestion, X } from 'lucide-react'
import { useEffect } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { useNow } from '@/components/Shell'
import { Button, EmptyState, Kbd, Panel, PanelHeader, SeverityBadge, Skeleton, Tag } from '@/components/ui'
import { api } from '@/lib/api'
import { clock, incidentId, pct, relTime, SEVERITY_COLOR, titleOf } from '@/lib/utils'
import { useIncidentAction } from './Command'

const DETAIL_LABELS: Record<string, string> = {
  people: 'People in view',
  vehicles: 'Vehicles involved',
  model_class: 'Model class',
  model_conf: 'Model confidence',
  vehicle_check: 'Vehicle check',
  rule: 'Trajectory rule',
  sources: 'Detection sources',
  object: 'Object',
  owner_track: 'Owner track ID',
  owner_away_s: 'Owner away (s)',
  stationary_s: 'Stationary (s)',
  people_nearby: 'Other people nearby',
  source: 'Detector',
  motion_ratio: 'Motion vs baseline',
  speed_max: 'Fastest person (body-heights/s)',
  limit: 'Occupancy limit',
  zone: 'Zone',
  zone_kind: 'Zone type',
  gate: 'Confidence gate applied',
}

function fmt(v: unknown): string {
  if (v === null || v === undefined) return 'n/a'
  if (Array.isArray(v)) return v.join(' + ')
  if (typeof v === 'number') return Number.isInteger(v) ? String(v) : v.toFixed(2)
  return String(v)
}

export function IncidentDetail() {
  const { id } = useParams()
  const iid = Number(id)
  const now = useNow()
  const nav = useNavigate()
  const act = useIncidentAction()
  const q = useQuery({ queryKey: ['incident', iid], queryFn: () => api.incident(iid), refetchInterval: (s) => (s.state.data?.clip ? false : 3000) })
  const inc = q.data

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!inc || e.metaKey || e.ctrlKey || e.altKey) return
      const k = e.key.toLowerCase()
      if (k === 'escape') nav('/')
      else if (k === 'c' && inc.status === 'new') act.mutate({ id: inc.id, action: 'confirm' })
      else if (k === 'd' && inc.status === 'new') act.mutate({ id: inc.id, action: 'dismiss' })
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [inc, act, nav])

  if (q.isLoading) {
    return (
      <div className="grid grid-cols-[minmax(0,1fr)_400px] gap-3 p-3">
        <Skeleton className="h-[420px] rounded-lg" />
        <Skeleton className="h-[420px] rounded-lg" />
      </div>
    )
  }
  if (!inc) {
    return (
      <EmptyState icon={FileQuestion} title="Incident not found" action={<Button asChild size="sm"><Link to="/">Back to command view</Link></Button>}>
        It may belong to an earlier session. Demo mode starts with an empty queue each time.
      </EmptyState>
    )
  }

  const color = SEVERITY_COLOR[inc.severity]
  const details = Object.entries(inc.details ?? {}).filter(([k]) => k in DETAIL_LABELS && k !== 'owner_text')

  return (
    <div className="mx-auto max-w-[1500px] p-3">
      <div className="mb-3 flex items-center justify-between gap-4">
        <div className="flex min-w-0 items-center gap-3">
          <Button asChild variant="ghost" size="icon" aria-label="Back to command view"><Link to="/"><ArrowLeft size={16} /></Link></Button>
          <SeverityBadge severity={inc.severity} />
          <h2 className="truncate text-[15px] font-semibold tracking-tight">{titleOf(inc)}</h2>
          <span className="num text-[12px] text-faint">{incidentId(inc.id)}</span>
          <Tag className="capitalize">{inc.status === 'new' ? 'Open' : inc.status}</Tag>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          {inc.status === 'new' ? (
            <>
              <Button variant="primary" disabled={act.isPending} onClick={() => act.mutate({ id: inc.id, action: 'confirm' })}><Check size={14} /> Confirm <Kbd>C</Kbd></Button>
              <Button disabled={act.isPending} onClick={() => act.mutate({ id: inc.id, action: 'dismiss' })}><X size={14} /> Dismiss <Kbd>D</Kbd></Button>
            </>
          ) : (
            <span className="text-[12px] capitalize text-muted">{inc.status} by operator</span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-[minmax(0,1fr)_400px] gap-3">
        <div className="space-y-3">
          <Panel>
            <PanelHeader title="Evidence clip" meta={inc.clip ? 'About 10 s before detection and 4 s after' : undefined} />
            <div className="bg-black">
              {inc.clip ? (
                <video key={inc.clip} src={inc.clip} controls autoPlay muted loop className="mx-auto aspect-[4/3] max-h-[460px] w-full object-contain" />
              ) : (
                <div className="flex aspect-[4/3] max-h-[460px] w-full flex-col items-center justify-center gap-2 text-faint">
                  <div className="skeleton h-1 w-28" />
                  <span className="text-[12px]">Writing the evidence clip. It appears a few seconds after detection.</span>
                </div>
              )}
            </div>
          </Panel>
          <div className="grid grid-cols-2 gap-3">
            <Panel>
              <PanelHeader title="Keyframe" meta="Frame that raised the incident, with boxes" />
              {inc.keyframe ? <img src={inc.keyframe} alt="Keyframe" className="w-full rounded-b-lg" /> : <Skeleton className="m-3 h-48" />}
            </Panel>
            <Panel>
              <PanelHeader title="Timeline" />
              <ol className="space-y-2.5 p-3">
                {(inc.timeline ?? []).map((t, i) => (
                  <li key={i} className="flex gap-3 text-[12px]">
                    <span className="num w-[58px] shrink-0 text-faint">{clock(t.t)}</span>
                    <span className="text-muted">{t.text}</span>
                  </li>
                ))}
              </ol>
            </Panel>
          </div>
        </div>

        <div className="space-y-3">
          <Panel>
            <PanelHeader title="Severity" meta="How the score was built" />
            <div className="flex items-end justify-between gap-3 px-3 pt-3">
              <div>
                <div className="num text-[30px] font-semibold leading-none" style={{ color }}>{Math.round(inc.score)}<span className="text-[13px] font-normal text-faint"> / 100</span></div>
                <div className="mt-1.5 text-[12px] text-muted">Critical 80+, High 60+, Medium 40+</div>
              </div>
              <div className="text-right text-[12px] text-muted">
                <div>Confidence <span className="num text-fg">{pct(inc.confidence)}</span></div>
                <div className="mt-0.5">First seen <span className="num text-fg">{relTime(inc.first_ts, now)}</span></div>
              </div>
            </div>
            <div className="mx-3 mt-3 h-1 overflow-hidden rounded-full bg-raised">
              <div className="h-full rounded-full transition-[width] duration-200" style={{ width: `${inc.score}%`, background: color }} />
            </div>
            <ul className="divide-y divide-line px-3 pb-1 pt-2">
              {inc.reasons.map((r) => (
                <li key={r.text} className="flex items-start justify-between gap-3 py-2 text-[12px] leading-snug">
                  <span className="text-fg">{r.text}</span>
                  <span className="num shrink-0 text-muted">+{r.points}</span>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel>
            <PanelHeader title="Cameras" meta={inc.area} />
            <ul className="divide-y divide-line px-3">
              {inc.cameras.map((c) => (
                <li key={c.id} className="flex items-center justify-between py-2 text-[12px]">
                  <span className="text-fg">{c.name}</span>
                  <span className="num text-muted">{pct(c.confidence)}</span>
                </li>
              ))}
            </ul>
            {inc.cameras.length > 1 && <p className="border-t border-line px-3 py-2 text-[12px] text-muted">Merged: same incident type in the same area within 30 s. Combined confidence rises with each camera.</p>}
          </Panel>

          <Panel>
            <PanelHeader title="Details" />
            {details.length ? (
              <dl className="divide-y divide-line px-3">
                {details.map(([k, v]) => (
                  <div key={k} className="flex items-start justify-between gap-4 py-2 text-[12px]">
                    <dt className="shrink-0 text-muted">{DETAIL_LABELS[k]}</dt>
                    <dd className="num text-right text-fg">{fmt(v)}</dd>
                  </div>
                ))}
              </dl>
            ) : (
              <p className="px-3 py-3 text-[12px] text-muted">No extra details recorded.</p>
            )}
          </Panel>

          <Panel>
            <PanelHeader title="Vision verification" />
            {!inc.verification ? (
              <p className="px-3 py-3 text-[12px] leading-relaxed text-muted">Off. Set VISION_VERIFY_ENABLED=1 and ANTHROPIC_API_KEY in .env to have three head-blurred frames checked by a vision model.</p>
            ) : inc.verification.status !== 'done' ? (
              <p className="px-3 py-3 text-[12px] leading-relaxed text-muted">No verdict: {String(inc.verification.error ?? 'unavailable')}. The incident stands on the detector's evidence alone.</p>
            ) : (
              <dl className="divide-y divide-line px-3">
                {([
                  ['Verdict', inc.verification.confirmed ? 'Confirmed' : 'Not confirmed'],
                  ['Sees', String(inc.verification.description)],
                  ['Because', String(inc.verification.reason)],
                  ['Its severity (1-5)', String(inc.verification.severity)],
                  ['Model', String(inc.verification.model)],
                ] as const).map(([k, v]) => (
                  <div key={k} className="flex items-start justify-between gap-4 py-2 text-[12px]">
                    <dt className="shrink-0 text-muted">{k}</dt>
                    <dd className="text-right text-fg">{v}</dd>
                  </div>
                ))}
              </dl>
            )}
          </Panel>
        </div>
      </div>
    </div>
  )
}
