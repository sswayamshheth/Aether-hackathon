import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Toaster } from 'sonner'
import { Shell } from '@/components/Shell'
import { TooltipProvider } from '@/components/ui'
import { Analytics } from '@/pages/Analytics'
import { Cameras } from '@/pages/Cameras'
import { Command } from '@/pages/Command'
import { IncidentDetail } from '@/pages/IncidentDetail'
import { Models } from '@/pages/Models'
import { Zones } from '@/pages/Zones'
import './index.css'

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 5_000, retry: 1, refetchOnWindowFocus: false } },
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={queryClient}>
      <TooltipProvider delayDuration={250}>
        <BrowserRouter>
          <Routes>
            <Route element={<Shell />}>
              <Route index element={<Command />} />
              <Route path="incidents/:id" element={<IncidentDetail />} />
              <Route path="cameras" element={<Cameras />} />
              <Route path="zones" element={<Zones />} />
              <Route path="analytics" element={<Analytics />} />
              <Route path="models" element={<Models />} />
            </Route>
          </Routes>
        </BrowserRouter>
        <Toaster
          theme="dark"
          position="bottom-right"
          offset={{ bottom: 48, right: 16 }}
          toastOptions={{
            style: { background: '#161c25', border: '1px solid #2a3442', color: '#e6eaf0', fontSize: 13, borderRadius: 8 },
          }}
        />
      </TooltipProvider>
    </QueryClientProvider>
  </StrictMode>,
)
