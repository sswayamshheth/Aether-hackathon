import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef, useState } from 'react'
import { toast } from 'sonner'
import type { Camera, Incident, Status } from './api'
import { titleOf } from './utils'

function wsUrl(path: string) {
  const proto = location.protocol === 'https:' ? 'wss' : 'ws'
  return `${proto}://${location.host}${path}`
}

/** One short two-tone beep for new critical incidents. No audio file needed. */
function beep() {
  try {
    const ctx = new AudioContext()
    const gain = ctx.createGain()
    gain.connect(ctx.destination)
    gain.gain.setValueAtTime(0.0001, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.12, ctx.currentTime + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.5)
    for (const [f, at] of [[880, 0], [660, 0.18]] as const) {
      const osc = ctx.createOscillator()
      osc.type = 'sine'
      osc.frequency.value = f
      osc.connect(gain)
      osc.start(ctx.currentTime + at)
      osc.stop(ctx.currentTime + at + 0.16)
    }
    setTimeout(() => ctx.close(), 800)
  } catch { /* audio blocked until the user interacts with the page */ }
}

/** Event socket: keeps status, cameras and incidents fresh in the query cache. */
export function useLiveEvents(soundOn: boolean) {
  const qc = useQueryClient()
  const [connected, setConnected] = useState(false)
  const sound = useRef(soundOn)
  sound.current = soundOn

  useEffect(() => {
    let ws: WebSocket | null = null
    let closed = false
    let retry: ReturnType<typeof setTimeout>

    const upsert = (inc: Incident) => {
      qc.setQueryData<Incident[]>(['incidents'], (old) => {
        if (!old) return old
        const i = old.findIndex((x) => x.id === inc.id)
        if (i === -1) return [inc, ...old]
        const next = old.slice()
        next[i] = inc
        return next
      })
      qc.setQueryData(['incident', inc.id], inc)
    }

    const connect = () => {
      ws = new WebSocket(wsUrl('/ws'))
      ws.onopen = () => setConnected(true)
      ws.onclose = () => {
        setConnected(false)
        if (!closed) retry = setTimeout(connect, 1500)
      }
      ws.onmessage = (e) => {
        const msg = JSON.parse(e.data)
        if (msg.type === 'status') {
          qc.setQueryData<Status>(['status'], msg.status)
          qc.setQueryData<Camera[]>(['cameras'], msg.cameras)
        } else if (msg.type === 'incident.new' || msg.type === 'incident.update') {
          const inc: Incident = msg.incident
          upsert(inc)
          if (msg.type === 'incident.new') {
            toast(`${inc.severity}: ${titleOf(inc)}`, {
              description: `${inc.area} · ${inc.cameras.map((c) => c.name).join(', ')}`,
            })
            if (inc.severity === 'Critical' && sound.current) beep()
          } else if (msg.alert && inc.severity === 'Critical' && sound.current) {
            beep()
          }
        }
      }
    }
    connect()
    return () => {
      closed = true
      clearTimeout(retry)
      ws?.close()
    }
  }, [qc])

  return connected
}

// ---- video: one binary socket for all cameras, fanned out to canvases
type Listener = (bmp: ImageBitmap) => void
const listeners = new Map<string, Set<Listener>>()
let videoWs: WebSocket | null = null
let videoUsers = 0
const decoder = new TextDecoder()

function openVideo() {
  videoWs = new WebSocket(wsUrl('/ws/video'))
  videoWs.binaryType = 'arraybuffer'
  videoWs.onmessage = async (e) => {
    const buf = e.data as ArrayBuffer
    const id = decoder.decode(new Uint8Array(buf, 0, 16)).trim()
    const subs = listeners.get(id)
    if (!subs?.size) return
    try {
      const bmp = await createImageBitmap(new Blob([buf.slice(16)], { type: 'image/jpeg' }))
      subs.forEach((fn) => fn(bmp))
    } catch { /* a torn frame; the next one replaces it */ }
  }
  videoWs.onclose = () => {
    videoWs = null
    if (videoUsers > 0) setTimeout(() => videoUsers > 0 && !videoWs && openVideo(), 1500)
  }
}

export function subscribeVideo(cameraId: string, fn: Listener) {
  if (!listeners.has(cameraId)) listeners.set(cameraId, new Set())
  listeners.get(cameraId)!.add(fn)
  videoUsers += 1
  if (!videoWs) openVideo()
  return () => {
    listeners.get(cameraId)?.delete(fn)
    videoUsers -= 1
    if (videoUsers === 0) {
      videoWs?.close()
      videoWs = null
    }
  }
}
