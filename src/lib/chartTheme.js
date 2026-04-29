export const DARK_THEME = {
  colors: {
    cpi:             '#cbd5e1',
    dnsFwd:          '#22d3ee',
    avg:             '#6366f1',
    slope:           '#22d3ee',
    curvature:       '#34d399',
    target:          'rgba(251,191,36,0.45)',
    whisker:         'rgba(148,163,184,0.30)',
    whiskerSelected: '#6366f1',
  },
  strokeWidths: {
    cpiLine:         1.5,
    dnsLine:         1.5,
    whiskerLine:     1,
    whiskerSelected: 1.5,
    selectedWhisker: 2.5,
  },
  ui: {
    grid:          'rgba(51,65,85,0.4)',
    axis:          'rgba(51,65,85,0.6)',
    tickLabel:     '#cbd5e1',
    tickFontSize:  10,
    tooltipBg:     '#0f172a',
    tooltipBorder: 'rgba(51,65,85,0.6)',
    tooltipText:   '#cbd5e1',
  },
}

export const LIGHT_THEME = {
  colors: {
    cpi:             '#334155',
    dnsFwd:          '#0891b2',
    avg:             '#4f46e5',
    slope:           '#0891b2',
    curvature:       '#059669',
    target:          'rgba(217,119,6,0.45)',
    whisker:         'rgba(100,116,139,0.30)',
    whiskerSelected: '#4f46e5',
  },
  strokeWidths: DARK_THEME.strokeWidths,
  ui: {
    grid:          'rgba(203,213,225,0.6)',
    axis:          'rgba(203,213,225,0.8)',
    tickLabel:     '#1e293b',
    tickFontSize:  10,
    tooltipBg:     '#ffffff',
    tooltipBorder: 'rgba(203,213,225,0.8)',
    tooltipText:   '#1e293b',
  },
}

export function getTheme(isDark) {
  return isDark ? DARK_THEME : LIGHT_THEME
}

export function getTooltipStyle(isDark) {
  const ui = isDark ? DARK_THEME.ui : LIGHT_THEME.ui
  return {
    backgroundColor: ui.tooltipBg,
    border:          `1px solid ${ui.tooltipBorder}`,
    borderRadius:    '6px',
    fontSize:        '11px',
    color:           ui.tooltipText,
  }
}

