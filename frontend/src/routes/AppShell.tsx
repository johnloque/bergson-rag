import { Outlet } from 'react-router-dom'
import { Sidebar } from '../components/Sidebar'

export function AppShell() {
  return (
    <div className="flex h-screen w-screen" style={{ background: 'var(--paper)' }}>
      <Sidebar />
      <main className="flex-1 overflow-y-auto">
        <Outlet />
      </main>
    </div>
  )
}
