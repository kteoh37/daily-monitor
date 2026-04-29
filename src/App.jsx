import { useState } from 'react'
import OverviewPanel from './components/OverviewPanel.jsx'
import ChartsPanel from './components/ChartsPanel.jsx'
import AboutPanel from './components/AboutPanel.jsx'
import { useDarkMode } from './lib/useDarkMode.jsx'

const TABS = [
  { id: 'overview', label: 'Overview', sub: 'Heatmap · Latest values' },
  { id: 'charts',   label: 'Charts',   sub: 'By country / theme' },
  { id: 'about',    label: 'About',    sub: 'Sources · Methodology' },
]

function SunIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="5"/>
      <line x1="12" y1="1" x2="12" y2="3"/>
      <line x1="12" y1="21" x2="12" y2="23"/>
      <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/>
      <line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
      <line x1="1" y1="12" x2="3" y2="12"/>
      <line x1="21" y1="12" x2="23" y2="12"/>
      <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/>
      <line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
    </svg>
  )
}

function MoonIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
    </svg>
  )
}

export default function App() {
  const [activeTab, setActiveTab] = useState('overview')
  const { isDark, toggle } = useDarkMode()
  const isOverview = activeTab === 'overview'

  return (
    <div className={`flex flex-col ${isOverview ? 'min-h-screen md:h-screen md:overflow-hidden' : 'min-h-screen'}`}>

      <header className="border-b border-slate-200 dark:border-slate-800 px-4 sm:px-6 py-3 sm:py-4">
        <div className="max-w-screen-2xl mx-auto flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 sm:gap-6">
          <div className="min-w-0">
            <h1 className="text-base font-semibold text-slate-900 dark:text-white leading-tight">
              Daily Market Monitor — Japan &amp; G7
            </h1>
            <p className="text-xs text-slate-500 mt-0.5">G7 + EA + Korea + Australia · sourced from haver-data</p>
          </div>
          <div className="flex items-start gap-2 flex-shrink-0">
            <nav className="grid grid-cols-3 gap-1.5 sm:flex sm:flex-wrap">
              {TABS.map(tab => (
                <button
                  key={tab.id}
                  onClick={() => setActiveTab(tab.id)}
                  className={`tab-btn text-center sm:text-left px-2 py-2 text-xs sm:px-5 sm:py-2.5 sm:text-sm leading-tight ${
                    activeTab === tab.id ? 'tab-btn-active' : 'tab-btn-inactive'
                  }`}
                >
                  <div>{tab.label}</div>
                  <div className={`text-xs mt-0.5 font-normal hidden sm:block ${
                    activeTab === tab.id ? 'text-indigo-300' : 'text-slate-400 dark:text-slate-600'
                  }`}>{tab.sub}</div>
                </button>
              ))}
            </nav>
            <button
              onClick={toggle}
              className="shrink-0 p-2 rounded-lg text-slate-500 hover:text-slate-700 hover:bg-slate-100 dark:text-slate-400 dark:hover:text-slate-200 dark:hover:bg-slate-800 transition-all"
              aria-label="Toggle dark/light mode"
            >
              {isDark ? <SunIcon /> : <MoonIcon />}
            </button>
          </div>
        </div>
      </header>

      <main className={`flex-1 px-4 sm:px-6 py-4 sm:py-5${isOverview ? ' md:overflow-hidden md:flex md:flex-col' : ''}`}>
        <div className={`max-w-screen-2xl mx-auto${isOverview ? ' w-full md:flex-1 md:overflow-hidden md:flex md:flex-col' : ''}`}>
          {activeTab === 'overview' && <OverviewPanel />}
          {activeTab === 'charts'   && <ChartsPanel />}
          {activeTab === 'about'    && <AboutPanel />}
        </div>
      </main>

    </div>
  )
}
