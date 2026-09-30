import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link2, Trash2, Upload, Video } from 'lucide-react'
import { useRef, useState, type DragEvent } from 'react'
import { toast } from 'sonner'
import { Button, EmptyState, Input, Label, Panel, PanelHeader, Segmented, Select, Skeleton, StatusDot, Tag } from '@/components/ui'
import { api, uploadCamera, type Camera } from '@/lib/api'
import { cn } from '@/lib/utils'

type Profile = Camera['profile']
const PROFILES: { value: Profile; label: string }[] = [
  { value: 'mixed', label: 'Mixed: accident, crowd, baggage' },
  { value: 'traffic', label: 'Traffic: accident' },
  { value: 'public', label: 'Public space: crowd, baggage' },
]
const PROFILE_SHORT: Record<Profile, string> = { mixed: 'Mixed', traffic: 'Traffic', public: 'Public space' }

function AddCamera() {
  const qc = useQueryClient()
  const [mode, setMode] = useState<'rtsp' | 'upload'>('rtsp')
  const [name, setName] = useState('')
  const [area, setArea] = useState('')
  const [url, setUrl] = useState('')
  const [profile, setProfile] = useState<Profile>('mixed')
  const [file, setFile] = useState<File | null>(null)
  const [progress, setProgress] = useState<number | null>(null)
  const [over, setOver] = useState(false)
  const picker = useRef<HTMLInputElement>(null)

  const done = (cam: Camera) => {
    qc.invalidateQueries({ queryKey: ['cameras'] })
    toast(`${cam.name} added`, { description: 'Connecting. The first frame usually arrives within a few seconds.' })
    setName(''); setArea(''); setUrl(''); setFile(null); setProgress(null)
  }
  const add = useMutation({ mutationFn: api.addCamera, onSuccess: done, onError: (e: Error) => toast.error(e.message) })

  const submit = async () => {
    if (mode === 'rtsp') {
      add.mutate({ name: name || 'Camera', source: url, area, profile })
      return
    }
    if (!file) return
    const form = new FormData()
    form.append('file', file)
    form.append('name', name || file.name.replace(/\.[^.]+$/, ''))
    form.append('area', area)
    form.append('profile', profile)
    setProgress(0)
    try {
      done(await uploadCamera(form, setProgress))
    } catch (e) {
      setProgress(null)
      toast.error((e as Error).message)
    }
  }

  const onDrop = (e: DragEvent) => {
    e.preventDefault()
    setOver(false)
    const f = e.dataTransfer.files?.[0]
    if (f) setFile(f)
  }
  const busy = add.isPending || progress !== null
  const ready = mode === 'rtsp' ? /^(rtsps?|https?):\/\/.+/i.test(url.trim()) : !!file

  return (
    <Panel className="self-start">
      <PanelHeader title="Add camera">
        <Segmented value={mode} onChange={setMode} options={[{ value: 'rtsp', label: 'Stream URL' }, { value: 'upload', label: 'Video file' }]} />
      </PanelHeader>
      <div className="space-y-3 p-3">
        {mode === 'rtsp' ? (
          <div>
            <Label hint="rtsp:// or http(s)://">Stream URL</Label>
            <Input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="rtsp://localhost:8554/cam1" spellCheck={false} className="num" />
          </div>
        ) : (
          <div>
            <Label hint="mp4, avi, mov, mkv, webm">Video file</Label>
            <div
              onDragOver={(e) => { e.preventDefault(); setOver(true) }}
              onDragLeave={() => setOver(false)}
              onDrop={onDrop}
              onClick={() => picker.current?.click()}
              className={cn('flex h-28 cursor-pointer flex-col items-center justify-center gap-1.5 rounded-md border border-dashed text-[12px] transition-colors duration-150', over ? 'border-accent bg-accent-soft text-fg' : 'border-line-strong text-muted hover:border-faint')}
            >
              <Upload size={16} strokeWidth={1.75} />
              {file ? (
                <span className="max-w-[90%] truncate text-fg">{file.name} <span className="num text-faint">{(file.size / 1e6).toFixed(1)} MB</span></span>
              ) : (
                <span>Drop a video here, or click to choose</span>
              )}
              <input ref={picker} type="file" accept="video/*,.mkv,.avi" hidden onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
            </div>
            {progress !== null && (
              <div className="mt-2">
                <div className="h-1 overflow-hidden rounded-full bg-raised"><div className="h-full bg-accent transition-[width] duration-150" style={{ width: `${progress}%` }} /></div>
                <div className="num mt-1 text-[11px] text-faint">{progress < 100 ? `Uploading ${progress}%` : 'Checking the file'}</div>
              </div>
            )}
          </div>
        )}
        <div className="grid grid-cols-2 gap-3">
          <div>
            <Label>Name</Label>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Gate 2 east" />
          </div>
          <div>
            <Label hint="used to merge cameras">Area</Label>
            <Input value={area} onChange={(e) => setArea(e.target.value)} placeholder="Concourse" />
          </div>
        </div>
        <div>
          <Label>What to look for</Label>
          <Select value={profile} onChange={setProfile} options={PROFILES} />
        </div>
        <Button variant="primary" className="w-full" disabled={!ready || busy} onClick={submit}>
          {mode === 'rtsp' ? <Link2 size={14} /> : <Upload size={14} />}
          {busy ? 'Adding' : mode === 'rtsp' ? 'Connect stream' : 'Upload and start'}
        </Button>
        <p className="text-[12px] leading-relaxed text-faint">Cameras that share an area name are treated as views of the same place: one incident seen by two of them is merged.</p>
      </div>
    </Panel>
  )
}

export function Cameras() {
  const qc = useQueryClient()
  const cams = useQuery({ queryKey: ['cameras'], queryFn: api.cameras })
  const remove = useMutation({
    mutationFn: api.removeCamera,
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['cameras'] }); toast('Camera removed') },
    onError: (e: Error) => toast.error(e.message),
  })

  return (
    <div className="mx-auto grid max-w-[1500px] grid-cols-[minmax(0,1fr)_360px] gap-3 p-3">
      <Panel>
        <PanelHeader title="Cameras" meta={cams.data ? `${cams.data.filter((c) => c.status === 'online').length} of ${cams.data.length} online` : undefined} />
        {cams.isLoading ? (
          <div className="space-y-2 p-3">{[0, 1, 2].map((i) => <Skeleton key={i} className="h-9" />)}</div>
        ) : !cams.data?.length ? (
          <EmptyState icon={Video} title="No cameras yet">Add a stream URL or upload a video on the right. To simulate RTSP feeds locally, run scripts\simulate_rtsp.ps1 and add rtsp://localhost:8554/cam1.</EmptyState>
        ) : (
          <table className="w-full text-left text-[12px]">
            <thead>
              <tr className="border-b border-line text-[11px] uppercase tracking-wider text-faint">
                <th className="h-8 px-3 font-medium">Camera</th>
                <th className="px-3 font-medium">Area</th>
                <th className="px-3 font-medium">Profile</th>
                <th className="px-3 font-medium">Source</th>
                <th className="px-3 text-right font-medium">FPS</th>
                <th className="px-3 text-right font-medium">Latency</th>
                <th className="w-10 px-3" />
              </tr>
            </thead>
            <tbody>
              {cams.data.map((c) => (
                <tr key={c.id} className="border-b border-line last:border-0 hover:bg-[#131922]">
                  <td className="h-11 px-3">
                    <div className="flex items-center gap-2">
                      <StatusDot status={c.status} />
                      <span className="text-[13px] font-medium text-fg">{c.name}</span>
                      {c.status !== 'online' && <span className="text-faint">{c.error || c.status}</span>}
                    </div>
                  </td>
                  <td className="px-3 text-muted">{c.area}</td>
                  <td className="px-3"><Tag>{PROFILE_SHORT[c.profile]}</Tag></td>
                  <td className="num max-w-[280px] truncate px-3 text-muted" title={c.source_label}>{c.source_label}</td>
                  <td className="num px-3 text-right text-fg">{c.status === 'online' ? c.fps.toFixed(1) : '0.0'}</td>
                  <td className="num px-3 text-right text-muted">{c.status === 'online' ? `${c.latency_ms} ms` : 'n/a'}</td>
                  <td className="px-3 text-right">
                    <Button variant="ghost" size="icon" aria-label={`Remove ${c.name}`} disabled={remove.isPending} onClick={() => remove.mutate(c.id)} className="h-7 w-7 hover:text-[#f87171]">
                      <Trash2 size={14} />
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Panel>
      <AddCamera />
    </div>
  )
}
