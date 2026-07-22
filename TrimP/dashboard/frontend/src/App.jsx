import { lazy, Suspense, useState, useEffect, useRef } from 'react'
import Sidebar from './components/Sidebar.jsx'
import { DEFAULT_DARK_PALETTE, DEFAULT_FONT_SIZE, DEFAULT_LIGHT_PALETTE, familyOf, isValidFontSize, isValidPalette } from './theme.js'
// OverviewDashboard is the default landing page (`home`/`optimize`) — kept eager
// so first paint doesn't wait on an extra chunk fetch. Every other route is
// code-split via React.lazy: each one only downloads/parses when the user
// actually navigates there, which is what keeps the initial bundle small.
import OverviewDashboard from './pages/OverviewDashboard.jsx'
import { REFRESH_EVENT } from './hooks/useApi.js'
import { useTrimPEnabled } from './components/TrimPSwitch.jsx'
import { Loading } from './components/Charts.jsx'

const Config = lazy(() => import('./pages/Config.jsx'))
const Repositories = lazy(() => import('./pages/Repositories.jsx'))
const SystemDesign = lazy(() => import('./pages/SystemDesign.jsx'))
const TrimPolicy = lazy(() => import('./pages/TrimPolicy.jsx'))
const DiffReview = lazy(() => import('./pages/DiffReview.jsx'))
const Feedback = lazy(() => import('./pages/Feedback.jsx'))
const LiveTest = lazy(() => import('./pages/LiveTest.jsx'))
const Alerts = lazy(() => import('./pages/Alerts.jsx'))
const ValidationCenter = lazy(() => import('./pages/ValidationCenter.jsx'))
const DarkModePrototypes = lazy(() => import('./pages/DarkModePrototypes.jsx'))
const Sessions = lazy(() => import('./pages/Sessions.jsx'))

export default function App() {
  if (new URLSearchParams(window.location.search).has('dark-prototypes')) {
    return <Suspense fallback={<Loading />}><DarkModePrototypes /></Suspense>
  }
  // Persistent page state (survives refresh)
  const [page, setPage] = useState(() => {
    return localStorage.getItem('TrimP_current_page') || 'home'
  })
  const [sidebarCollapsed, setSidebarCollapsed] = useState(() => localStorage.getItem('TrimP_sidebar_collapsed') === 'true')
  const [savedPalette, setSavedPalette] = useState(() => {
    const stored = localStorage.getItem('TrimP_palette')
    if (stored && isValidPalette(stored)) return stored
    // Migrate anyone on the old boolean light/dark toggle to the matching named palette.
    return localStorage.getItem('TrimP_theme') === 'light' ? DEFAULT_LIGHT_PALETTE : DEFAULT_DARK_PALETTE
  })
  // Trying a theme doesn't commit it — previewPalette is what's actually on
  // screen right now (activePalette below); it's only written to localStorage
  // once the user explicitly saves it, so browsing all 7 themes is free and
  // always reversible.
  const [previewPalette, setPreviewPalette] = useState(null)
  const activePalette = previewPalette || savedPalette
  const isPreviewing = previewPalette !== null && previewPalette !== savedPalette
  const darkMode = familyOf(activePalette) === 'dark'
  // Remembers the last SAVED palette used in each family, so the sidebar's
  // quick dark/light toggle restores your specific choice (e.g. Darcula)
  // instead of always resetting to the family default.
  const lastPaletteRef = useRef({
    dark: familyOf(savedPalette) === 'dark' ? savedPalette : DEFAULT_DARK_PALETTE,
    light: familyOf(savedPalette) === 'light' ? savedPalette : DEFAULT_LIGHT_PALETTE,
  })
  const [fontSize, setFontSizeState] = useState(() => {
    const stored = localStorage.getItem('TrimP_font_size')
    return stored && isValidFontSize(stored) ? stored : DEFAULT_FONT_SIZE
  })
  const { enabled: optimizerEnabled } = useTrimPEnabled()

  // Save page to localStorage on change
  useEffect(() => {
    localStorage.setItem('TrimP_current_page', page)
  }, [page])

  useEffect(() => {
    localStorage.setItem('TrimP_sidebar_collapsed', String(sidebarCollapsed))
  }, [sidebarCollapsed])

  // The active palette (saved, or a live preview) is what actually paints
  // the app — this runs on every preview click too, so trying a theme is
  // instant and full-app, not a thumbnail.
  useEffect(() => {
    document.documentElement.dataset.theme = darkMode ? 'dark' : 'light'
    document.documentElement.dataset.palette = activePalette
  }, [activePalette, darkMode])

  useEffect(() => {
    document.documentElement.dataset.fontSize = fontSize
    localStorage.setItem('TrimP_font_size', fontSize)
  }, [fontSize])

  function setFontSize(id) {
    if (isValidFontSize(id)) setFontSizeState(id)
  }

  useEffect(() => {
    localStorage.setItem('TrimP_palette', savedPalette)
    localStorage.setItem('TrimP_theme', familyOf(savedPalette) === 'dark' ? 'dark' : 'light')
    lastPaletteRef.current[familyOf(savedPalette)] = savedPalette
  }, [savedPalette])

  function previewTheme(id) {
    setPreviewPalette(id)
  }
  function saveTheme() {
    if (previewPalette) setSavedPalette(previewPalette)
    setPreviewPalette(null)
  }
  function cancelPreview() {
    setPreviewPalette(null)
  }
  function toggleFamily() {
    // A quick, immediate switch — saves right away rather than previewing,
    // since it's a simple binary choice the user already trusts.
    const nextFamily = darkMode ? 'light' : 'dark'
    setPreviewPalette(null)
    setSavedPalette(lastPaletteRef.current[nextFamily])
  }

  useEffect(() => {
    const timer = window.setInterval(() => {
      if (document.visibilityState !== 'hidden') {
        window.dispatchEvent(new CustomEvent(REFRESH_EVENT, { detail: { at: Date.now() } }))
      }
    }, 1000)
    return () => window.clearInterval(timer)
  }, [])

  const pages = { 
    home: OverviewDashboard,
    optimize: OverviewDashboard,
    system: SystemDesign,
    policy: TrimPolicy,
    diff: DiffReview,
    demo: LiveTest,
    validation: ValidationCenter,
    activity: Repositories,
    sessions: Sessions,
    settings: Config,
    feedback: Feedback,
    alerts: Alerts,
  }
  
  const Page = pages[page] || OverviewDashboard

  return (
    <div className={`app-shell ${darkMode ? 'theme-dark' : 'theme-light'} ${sidebarCollapsed ? 'is-sidebar-collapsed' : ''}`}>
      <Sidebar
        active={page} onNavigate={setPage} collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(value => !value)}
        darkMode={darkMode} onToggleDarkMode={toggleFamily}
        palette={activePalette} savedPalette={savedPalette} isPreviewing={isPreviewing}
        onPreviewTheme={previewTheme} onSaveTheme={saveTheme} onCancelPreview={cancelPreview}
        optimizerEnabled={optimizerEnabled}
      />
      <div className="main-content" style={{ flex: 1, overflowY: 'auto' }}>
        <Suspense fallback={<Loading />}>
          <Page
            onNavigate={setPage} darkMode={darkMode}
            palette={activePalette} savedPalette={savedPalette} isPreviewing={isPreviewing}
            onPreviewTheme={previewTheme} onSaveTheme={saveTheme} onCancelPreview={cancelPreview}
            fontSize={fontSize} onSetFontSize={setFontSize}
          />
        </Suspense>
      </div>
    </div>
  )
}
