import { useEffect, useRef, useState } from 'react'
import { VideoOff } from 'lucide-react'
import type { Camera } from '@/lib/api'
import { subscribeVideo } from '@/lib/live'
import { cn } from '@/lib/utils'
import { StatusDot } from './ui'

/** Live annotated frames for one camera, drawn from the shared video socket. */
export function CameraFeed({ camera, className, onClick, alert }: { camera: Camera; className?: string; onClick?: () => void; alert?: boolean }) {
  const canvas = useRef<HTMLCanvasElement>(null)
  const [hasFrame, setHasFrame] = useState(false)

  useEffect(() => {
    setHasFrame(false)
    return subscribeVideo(camera.id, (bmp) => {
      const c = canvas.current
      if (!c) return
      if (c.width !== bmp.width || c.height !== bmp.height) {
        c.width = bmp.width
        c.height = bmp.height
      }
      c.getContext('2d')?.drawImage(bmp, 0, 0)
      bmp.close()
      setHasFrame(true)
    })
  }, [camera.id])

  const offline = camera.status !== 'online'
  return (
    <div
      onClick={onClick}
      className={cn(
        'group relative overflow-hidden rounded-lg border bg-black transition-colors duration-150',
        alert ? 'border-critical/70' : 'border-line',
        onClick && 'cursor-pointer hover:border-line-strong',
        className,
      )}
    >
      <canvas ref={canvas} className={cn('h-full w-full object-contain', !hasFrame && 'invisible')} />
      {!hasFrame && (
        <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 bg-surface text-faint">
          {offline && camera.status !== 'connecting' ? <VideoOff size={18} strokeWidth={1.75} /> : <div className="skeleton h-1 w-24" />}
          <span className="text-[12px]">
            {camera.status === 'offline' ? camera.error || 'Stream offline' : camera.status === 'reconnecting' ? 'Reconnecting' : 'Waiting for first frame'}
          </span>
        </div>
      )}
      <div className="pointer-events-none absolute inset-x-0 top-0 flex items-center justify-between gap-2 bg-gradient-to-b from-black/70 to-transparent px-2.5 pb-4 pt-2">
        <div className="flex min-w-0 items-center gap-2">
          <StatusDot status={camera.status} />
          <span className="truncate text-[12px] font-medium text-white">{camera.name}</span>
          <span className="truncate text-[11px] text-white/55">{camera.area}</span>
        </div>
        <span className="num shrink-0 text-[11px] text-white/70">{camera.status === 'online' ? `${camera.fps.toFixed(1)} fps` : camera.status}</span>
      </div>
    </div>
  )
}
