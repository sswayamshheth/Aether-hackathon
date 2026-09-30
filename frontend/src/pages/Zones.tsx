import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { PenLine, RotateCcw, Trash2, Undo2 } from 'lucide-react'
import { useEffect, useState, type MouseEvent } from 'react'
import { toast } from 'sonner'
import { Button, EmptyState, Input, Label, Panel, PanelHeader, Select, Skeleton } from '@/components/ui'
import { api, type ZoneKind } from '@/lib/api'

const KINDS: { value: ZoneKind; label: string; color: string; help: string }[] = [
  { value: 'restricted', label: 'Restricted area', color: '#ef4444', help: 'Baggage left here scores higher.' },
  { value: 'lane', label: 'Traffic lane', color: '#a0a8b4', help: 'Labels accident incidents with the lane name.' },
  { value: 'crowd', label: 'Crowd zone', color: '#3b82f6', help: 'Labels crowd incidents with the zone name.' },
  { value: 'ignore', label: 'Ignore (mask)', color: '#6b7280', help: 'Detections here are suppressed and logged.' },
]
const COLOR = Object.fromEntries(KINDS.map((k) => [k.value, k.color])) as Record<ZoneKind, string>

export function Zones() {
  const qc = useQueryClient()
  const cams = useQuery({ queryKey: ['cameras'], queryFn: api.cameras })
  const zones = useQuery({ queryKey: ['zones'], queryFn: api.zones })
  const [camId, setCamId] = useState('')
  const [kind, setKind] = useState<ZoneKind>('restricted')
  const [name, setName] = useState('')
  const [pts, setPts] = useState<[number, number][]>([])
  const [shot, setShot] = useState(0)
  const [imgOk, setImgOk] = useState(true)

  useEffect(() => {
    if (!camId && cams.data?.length) setCamId(cams.data[0].id)
  }, [cams.data, camId])
  useEffect(() => { setPts([]); setImgOk(true) }, [camId])

  const save = useMutation({
    mutationFn: () => api.addZone({ camera_id: camId, name: name || KINDS.find((k) => k.value === kind)!.label, kind, points: pts }),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['zones'] }); setPts([]); setName(''); toast('Zone saved', { description: 'It applies to new frames immediately.' }) },
    onError: (e: Error) => toast.error(e.message),
  })
  const remove = useMutation({
    mutationFn: api.removeZone,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['zones'] }); toast('Zone removed') },
  })

  const click = (e: MouseEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect()
    setPts((p) => [...p, [+((e.clientX - r.left) / r.width).toFixed(4), +((e.clientY - r.top) / r.height).toFixed(4)]])
  }

  const mine = (zones.data ?? []).filter((z) => z.camera_id === camId)
  const poly = (p: [number, number][]) => p.map(([x, y]) => `${x * 100},${y * 100}`).join(' ')

  if (cams.isLoading) return <div className="p-3"><Skeleton className="h-[480px] rounded-lg" /></div>
  if (!cams.data?.length) {
    return <EmptyState icon={PenLine} title="No cameras to draw on">Add a camera first. Zones are drawn on a live frame from that camera.</EmptyState>
  }

  return (
    <div className="mx-auto grid max-w-[1500px] grid-cols-[minmax(0,1fr)_340px] gap-3 p-3">
      <Panel>
        <PanelHeader title="Zone editor" meta="Click on the frame to place points. Three or more make a zone.">
          <Button size="sm" variant="ghost" onClick={() => setShot((s) => s + 1)}><RotateCcw size={13} /> New frame</Button>
        </PanelHeader>
        <div className="relative bg-black">
          {imgOk ? (
            <img key={`${camId}-${shot}`} src={`/api/cameras/${camId}/snapshot?t=${shot}`} alt="Camera frame" onError={() => setImgOk(false)} className="block w-full select-none" draggable={false} />
          ) : (
            <div className="flex aspect-[4/3] items-center justify-center text-[12px] text-faint">
              No frame from this camera yet.
              <button className="ml-2 text-accent hover:underline" onClick={() => { setImgOk(true); setShot((s) => s + 1) }}>Retry</button>
            </div>
          )}
          <svg viewBox="0 0 100 100" preserveAspectRatio="none" onClick={click} className="absolute inset-0 h-full w-full cursor-crosshair">
            {mine.map((z) => (
              <polygon key={z.id} points={poly(z.points)} fill={COLOR[z.kind]} fillOpacity={0.14} stroke={COLOR[z.kind]} strokeWidth={1.5} vectorEffect="non-scaling-stroke" />
            ))}
            {pts.length > 0 && (
              <>
                <polyline points={poly(pts)} fill={pts.length > 2 ? COLOR[kind] : 'none'} fillOpacity={0.12} stroke={COLOR[kind]} strokeWidth={1.5} strokeDasharray="4 3" vectorEffect="non-scaling-stroke" />
                {pts.map(([x, y], i) => (
                  <rect key={i} x={x * 100 - 0.45} y={y * 100 - 0.6} width={0.9} height={1.2} fill="#fff" stroke={COLOR[kind]} strokeWidth={1} vectorEffect="non-scaling-stroke" />
                ))}
              </>
            )}
          </svg>
        </div>
      </Panel>

      <div className="space-y-3 self-start">
        <Panel>
          <PanelHeader title="New zone" />
          <div className="space-y-3 p-3">
            <div>
              <Label>Camera</Label>
              <Select value={camId} onChange={setCamId} options={cams.data.map((c) => ({ value: c.id, label: c.name }))} />
            </div>
            <div>
              <Label>Type</Label>
              <Select value={kind} onChange={setKind} options={KINDS.map((k) => ({ value: k.value, label: k.label }))} />
              <p className="mt-1.5 text-[12px] text-faint">{KINDS.find((k) => k.value === kind)!.help}</p>
            </div>
            <div>
              <Label>Name</Label>
              <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Platform edge" />
            </div>
            <div className="flex items-center gap-2">
              <Button variant="primary" className="flex-1" disabled={pts.length < 3 || save.isPending} onClick={() => save.mutate()}>
                Save zone <span className="num text-white/70">{pts.length} pts</span>
              </Button>
              <Button size="icon" aria-label="Undo last point" disabled={!pts.length} onClick={() => setPts((p) => p.slice(0, -1))}><Undo2 size={14} /></Button>
            </div>
          </div>
        </Panel>
        <Panel>
          <PanelHeader title="Zones on this camera" meta={String(mine.length)} />
          {mine.length === 0 ? (
            <p className="px-3 py-4 text-[12px] leading-relaxed text-muted">None yet. Without zones the whole frame is monitored.</p>
          ) : (
            <ul className="divide-y divide-line">
              {mine.map((z) => (
                <li key={z.id} className="flex h-10 items-center justify-between gap-2 px-3">
                  <div className="flex min-w-0 items-center gap-2">
                    <span className="h-2 w-2 shrink-0 rounded-[2px]" style={{ background: COLOR[z.kind] }} />
                    <span className="truncate text-[13px] text-fg">{z.name}</span>
                    <span className="text-[12px] text-faint">{KINDS.find((k) => k.value === z.kind)?.label}</span>
                  </div>
                  <Button variant="ghost" size="icon" className="h-7 w-7 hover:text-[#f87171]" aria-label={`Delete ${z.name}`} onClick={() => remove.mutate(z.id)}><Trash2 size={14} /></Button>
                </li>
              ))}
            </ul>
          )}
        </Panel>
      </div>
    </div>
  )
}
