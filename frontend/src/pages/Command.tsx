import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ArrowUpRight, Check, Inbox, Maximize2, Minimize2, Video, X } from 'lucide-react'
import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { CameraFeed } from '@/components/CameraFeed'
import { useNow } from '@/components/Shell'
import { Button, EmptyState, Kbd, Segmented, SeverityBadge, Skeleton } from '@/components/ui'
import { api, type Incident, type IncidentStatus } from '@/lib/api'
import { cn, incidentId, relTime, SEVERITY_COLOR, titleOf } from '@/lib/utils'

export function useIncidentAction() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: ({ id, action }: { id: number; action: 'confirm' | 'dismiss' }) => api.act(id, action),
    onSuccess: (inc, { action }) => {
      qc.setQueryData<Incident[]>(['incidents'], (old) => old?.map((x) => (x.id === inc.id ? inc : x)))
      qc.setQueryData(['incident', inc.id], inc)
      qc.invalidateQueries({ queryKey: ['status'] })
      toast(action === 'confirm' ? `${incidentId(inc.id)} confirmed` : `${incidentId(inc.id)} dismissed`, {
        description: action === 'dismiss' ? 'The detection gate for this camera was raised.' : undefined,
      })
    },
    onError: (e: Error) => toast.error(`Action failed: ${e.message}`),
  })
}

function QueueRow({ inc, selected, onSelect, now }: { inc: Incident; selected: boolean; onSelect: () => void; now: number }) {
  const act = useIncidentAction()
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (selected) ref.current?.scrollIntoView({ block: 'nearest' })
  }, [selected])
  const top = inc.reasons.filter((r) => !r.text.includes('base score')).sort((a, b) => b.points - a.points)

  return (
    <div
      ref={ref}
      onClick={onSelect}
      className={cn('row-in relative cursor-pointer border-b border-line px-3 py-2.5 transition-colors duration-150', selected ? 'bg-raised' : 'hover:bg-[#131922]')}
    >
      <span className="absolute inset-y-0 left-0 w-[3px]" style={{ background: SEVERITY_COLOR[inc.severity], opacity: inc.status === 'new' ? 1 : 0.35 }} />
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <SeverityBadge severity={inc.severity} />
          <span className="truncate text-[13px] font-medium text-fg">{titleOf(inc)}</span>
        </div>
        <span className="num shrink-0 text-[12px] text-muted">{Math.round(inc.score)}</span>
      </div>
      <div className="mt-1 flex items-center justify-between gap-2 text-[12px] text-muted">
        <span className="truncate">
          {!inc.cameras.some((c) => c.name === inc.area) && (
            <>
              {inc.area}
              <span className="text-faint"> · </span>
            </>
          )}
          {inc.cameras.map((c) => c.name).join(', ')}
        </span>
        <span className="num shrink-0 text-faint">{relTime(inc.first_ts, now)}</span>
      </div>
      {selected && (
        <div className="mt-2.5">
          <div className="flex gap-2.5">
            {inc.keyframe ? (
              <img src={inc.keyframe} alt="" className="h-[68px] w-[104px] shrink-0 rounded-sm border border-line object-cover" />
            ) : (
              <Skeleton className="h-[68px] w-[104px] shrink-0" />
            )}
            <ul className="min-w-0 flex-1 space-y-1">
              {top.slice(0, 3).map((r) => (
                <li key={r.text} className="flex items-start justify-between gap-2 text-[12px] leading-snug">
                  <span className="text-muted">{r.text}</span>
                  <span className="num shrink-0 text-faint">+{r.points}</span>
                </li>
              ))}
            </ul>
          </div>
          <div className="mt-2.5 flex items-center justify-between">
            <div className="flex items-center gap-1.5">
              {inc.status === 'new' ? (
                <>
                  <Button size="sm" variant="primary" disabled={act.isPending} onClick={(e) => { e.stopPropagation(); act.mutate({ id: inc.id, action: 'confirm' }) }}>
                    <Check size={13} /> Confirm
                  </Button>
                  <Button size="sm" disabled={act.isPending} onClick={(e) => { e.stopPropagation(); act.mutate({ id: inc.id, action: 'dismiss' }) }}>
                    <X size={13} /> Dismiss
                  </Button>
                </>
              ) : (
                <span className="text-[12px] capitalize text-faint">{inc.status} by operator</span>
              )}
            </div>
            <Link to={`/incidents/${inc.id}`} onClick={(e) => e.stopPropagation()} className="flex items-center gap-1 text-[12px] text-accent hover:underline">
              <span className="num">{incidentId(inc.id)}</span> <ArrowUpRight size={13} />
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}

export function Command() {
  const now = useNow()
  const nav = useNavigate()
  const act = useIncidentAction()
  const cams = useQuery({ queryKey: ['cameras'], queryFn: api.cameras })
  const incs = useQuery({ queryKey: ['incidents'], queryFn: api.incidents, refetchInterval: 15_000 })
  const [tab, setTab] = useState<IncidentStatus>('new')
  const [selected, setSelected] = useState<number | null>(null)
  const [focus, setFocus] = useState<string | null>(null)

  const counts = useMemo(() => {
    const c = { new: 0, confirmed: 0, dismissed: 0 }
    incs.data?.forEach((i) => (c[i.status] += 1))
    return c
  }, [incs.data])

  const queue = useMemo(
    () => (incs.data ?? []).filter((i) => i.status === tab).sort((a, b) => b.score - a.score || b.last_ts - a.last_ts),
    [incs.data, tab],
  )
  const alerting = useMemo(() => {
    const ids = new Set<string>()
    incs.data?.filter((i) => i.status === 'new' && now - i.last_ts < 20).forEach((i) => i.cameras.forEach((c) => ids.add(c.id)))
    return ids
  }, [incs.data, now])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      if (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || e.metaKey || e.ctrlKey || e.altKey) return
      const idx = queue.findIndex((i) => i.id === selected)
      const cur = queue[idx]
      const k = e.key.toLowerCase()
      if (k === 'j') setSelected(queue[Math.min(queue.length - 1, idx + 1)]?.id ?? null)
      else if (k === 'k') setSelected(queue[Math.max(0, idx - 1)]?.id ?? queue[0]?.id ?? null)
      else if (k === 'enter' && cur) nav(`/incidents/${cur.id}`)
      else if (k === 'c' && cur?.status === 'new') act.mutate({ id: cur.id, action: 'confirm' })
      else if (k === 'd' && cur?.status === 'new') act.mutate({ id: cur.id, action: 'dismiss' })
      else if (k === 'escape') setFocus(null)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [queue, selected, act, nav])

  const list = cams.data ?? []
  const focused = list.find((c) => c.id === focus)
  const cols = list.length <= 1 ? 1 : list.length <= 4 ? 2 : 3

  return (
    <div className="flex h-full">
      <section className="flex min-w-0 flex-1 flex-col p-3">
        {cams.isLoading ? (
          <div className="grid flex-1 grid-cols-2 gap-3">
            {[0, 1, 2, 3].map((i) => <Skeleton key={i} className="rounded-lg" />)}
          </div>
        ) : list.length === 0 ? (
          <div className="flex-1 rounded-lg border border-dashed border-line">
            <EmptyState icon={Video} title="No cameras yet" action={<Button asChild variant="primary" size="sm"><Link to="/cameras">Add a camera</Link></Button>}>
              Add an RTSP stream or upload a video file. Detections appear here as soon as the first frame arrives.
            </EmptyState>
          </div>
        ) : focused ? (
          <div className="flex min-h-0 flex-1 flex-col gap-3">
            <div className="relative min-h-0 flex-1">
              <CameraFeed camera={focused} className="h-full" alert={alerting.has(focused.id)} />
              <Button size="sm" className="absolute bottom-2.5 right-2.5" onClick={() => setFocus(null)}>
                <Minimize2 size={13} /> Wall <Kbd>Esc</Kbd>
              </Button>
            </div>
            <div className="flex h-24 shrink-0 gap-3">
              {list.filter((c) => c.id !== focused.id).map((c) => (
                <CameraFeed key={c.id} camera={c} className="aspect-[4/3] h-full" onClick={() => setFocus(c.id)} alert={alerting.has(c.id)} />
              ))}
            </div>
          </div>
        ) : (
          <div className="grid min-h-0 flex-1 gap-3" style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`, gridAutoRows: 'minmax(0, 1fr)' }}>
            {list.map((c) => (
              <div key={c.id} className="relative min-h-0">
                <CameraFeed camera={c} className="h-full" onClick={() => setFocus(c.id)} alert={alerting.has(c.id)} />
                <Maximize2 size={13} className="pointer-events-none absolute bottom-2.5 right-2.5 text-white/0 transition-colors duration-150 [div:hover>&]:text-white/70" />
              </div>
            ))}
          </div>
        )}
      </section>

      <aside className="flex w-[384px] shrink-0 flex-col border-l border-line bg-surface">
        <div className="flex h-11 shrink-0 items-center justify-between border-b border-line px-3">
          <h2 className="text-[13px] font-semibold">Incident queue</h2>
          <Segmented
            value={tab}
            onChange={(v) => { setTab(v); setSelected(null) }}
            options={[
              { value: 'new', label: 'Open', count: counts.new },
              { value: 'confirmed', label: 'Confirmed', count: counts.confirmed },
              { value: 'dismissed', label: 'Dismissed', count: counts.dismissed },
            ]}
          />
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto">
          {incs.isLoading ? (
            <div className="space-y-px">
              {[0, 1, 2].map((i) => (
                <div key={i} className="space-y-2 border-b border-line px-3 py-3">
                  <Skeleton className="h-4 w-2/3" />
                  <Skeleton className="h-3 w-1/2" />
                </div>
              ))}
            </div>
          ) : incs.isError ? (
            <EmptyState icon={Inbox} title="Could not load incidents" action={<Button size="sm" onClick={() => incs.refetch()}>Retry</Button>}>
              The backend did not answer. Check that it is running on port 8000.
            </EmptyState>
          ) : queue.length === 0 ? (
            <EmptyState icon={Inbox} title={tab === 'new' ? 'No open incidents' : `No ${tab} incidents`}>
              {tab === 'new' ? 'Accident, crowd and baggage detections that pass the false-alarm filter are listed here, highest severity first.' : 'Incidents you act on move here.'}
            </EmptyState>
          ) : (
            queue.map((inc) => <QueueRow key={inc.id} inc={inc} now={now} selected={selected === inc.id} onSelect={() => setSelected(selected === inc.id ? null : inc.id)} />)
          )}
        </div>
        <div className="flex h-9 shrink-0 items-center gap-3 border-t border-line px-3 text-[11px] text-faint">
          <span className="flex items-center gap-1"><Kbd>J</Kbd><Kbd>K</Kbd> move</span>
          <span className="flex items-center gap-1"><Kbd>C</Kbd> confirm</span>
          <span className="flex items-center gap-1"><Kbd>D</Kbd> dismiss</span>
          <span className="flex items-center gap-1"><Kbd>Enter</Kbd> open</span>
        </div>
      </aside>
    </div>
  )
}
