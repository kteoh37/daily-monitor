import { createContext, useContext, useEffect, useState } from 'react'

const DarkModeContext = createContext({ isDark: false, toggle: () => {} })

export function DarkModeProvider({ children }) {
  const [isDark, setIsDark] = useState(() => {
    try {
      const stored = localStorage.getItem('daily-monitor-theme')
      return stored ? stored === 'dark' : false
    } catch {
      return false
    }
  })

  useEffect(() => {
    document.documentElement.classList.toggle('dark', isDark)
    try { localStorage.setItem('daily-monitor-theme', isDark ? 'dark' : 'light') } catch {}
  }, [isDark])

  return (
    <DarkModeContext.Provider value={{ isDark, toggle: () => setIsDark(d => !d) }}>
      {children}
    </DarkModeContext.Provider>
  )
}

export function useDarkMode() {
  return useContext(DarkModeContext)
}
