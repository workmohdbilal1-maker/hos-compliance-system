import { Link, useLocation } from 'react-router-dom'
import { Truck, Plus, LayoutDashboard } from 'lucide-react'

export default function Header() {
  const location = useLocation()

  const isActive = (path: string) =>
    location.pathname === path ? 'bg-primary-700' : 'hover:bg-primary-600'

  return (
    <header className="bg-primary-800 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <Link to="/" className="flex items-center space-x-3">
            <Truck className="h-8 w-8" />
            <div>
              <h1 className="text-lg font-bold leading-tight">ELD Trip Planner</h1>
              <p className="text-xs text-primary-200">FMCSA HOS Compliance</p>
            </div>
          </Link>

          <nav className="flex items-center space-x-1">
            <Link
              to="/"
              className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${isActive('/')}`}
            >
              <LayoutDashboard className="h-4 w-4" />
              <span>Dashboard</span>
            </Link>
            <Link
              to="/trips/new"
              className={`flex items-center space-x-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${isActive('/trips/new')}`}
            >
              <Plus className="h-4 w-4" />
              <span>New Trip</span>
            </Link>
          </nav>
        </div>
      </div>
    </header>
  )
}
