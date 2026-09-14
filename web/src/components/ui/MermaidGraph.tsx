import React, { useEffect, useRef, useState } from 'react'
import mermaid from 'mermaid'
import { Download, Eye, EyeOff } from 'lucide-react'
import { Button } from './Button'

interface MermaidGraphProps {
  content: string
  className?: string
  isDark?: boolean
}

export const MermaidGraph: React.FC<MermaidGraphProps> = ({
  content,
  className = '',
  isDark = true,
}) => {
  const [svgContent, setSvgContent] = useState<string | null>(null)
  const [renderError, setRenderError] = useState<string | null>(null)
  const [visible, setVisible] = useState(true)

  useEffect(() => {
    let diagram = content.trim()
    const match = diagram.match(/```mermaid\s*([\s\S]*?)```/)
    if (match) {
      diagram = match[1].trim()
    }

    if (!diagram || (!diagram.startsWith('graph') && !diagram.startsWith('flowchart'))) {
      setSvgContent(null)
      return
    }

    mermaid.initialize({
      startOnLoad: false,
      theme: isDark ? 'dark' : 'default',
      themeVariables: isDark
        ? {
            darkMode: true,
            background: '#1c1c1e',
            primaryColor: '#2c2c2e',
            primaryTextColor: '#f2f2f7',
            primaryBorderColor: '#3a3a3c',
            lineColor: '#8e8e93',
            secondaryColor: '#2c2c2e',
            tertiaryColor: '#1c1c1e',
          }
        : {
            darkMode: false,
            background: '#ffffff',
            primaryColor: '#f5f5f7',
            primaryTextColor: '#1c1c1e',
            primaryBorderColor: '#e5e5ea',
            lineColor: '#8e8e93',
            secondaryColor: '#f5f5f7',
            tertiaryColor: '#ffffff',
          },
      securityLevel: 'loose',
    })

    const id = `mermaid-${Math.random().toString(36).substring(2, 9)}`
    mermaid
      .render(id, diagram)
      .then(({ svg }) => {
        setSvgContent(svg)
        setRenderError(null)
      })
      .catch(() => {
        setRenderError('Could not render relationship graph diagram.')
        setSvgContent(null)
      })
  }, [content, isDark])

  const handleDownloadPng = () => {
    if (!svgContent) return
    const svgBlob = new Blob([svgContent], { type: 'image/svg+xml;charset=utf-8' })
    const url = URL.createObjectURL(svgBlob)
    const img = new Image()
    img.onload = () => {
      const canvas = document.createElement('canvas')
      const w = img.naturalWidth || 900
      const h = img.naturalHeight || 600
      canvas.width = w * 2
      canvas.height = h * 2
      const ctx = canvas.getContext('2d')
      if (ctx) {
        ctx.scale(2, 2)
        ctx.fillStyle = isDark ? '#1c1c1e' : '#ffffff'
        ctx.fillRect(0, 0, w, h)
        ctx.drawImage(img, 0, 0, w, h)
        const pngUrl = canvas.toDataURL('image/png')
        const link = document.createElement('a')
        link.href = pngUrl
        link.download = 'character_graph.png'
        document.body.appendChild(link)
        link.click()
        document.body.removeChild(link)
      }
      URL.revokeObjectURL(url)
    }
    img.src = url
  }

  if (renderError || !svgContent) {
    return (
      <div className="p-4 text-xs text-muted-foreground bg-secondary/50 rounded-2xl">
        {renderError || 'Diagram preview unavailable. Showing raw data below.'}
      </div>
    )
  }

  return (
    <div className={`space-y-3 ${className}`}>
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
          Relationship Visualizer
        </span>
        <div className="flex items-center gap-2">
          <Button
            size="icon"
            variant="secondary"
            onClick={() => setVisible(!visible)}
            className="h-8 w-8 rounded-full flex items-center justify-center shrink-0"
            title={visible ? 'Hide Graph' : 'Show Graph'}
          >
            {visible ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
          </Button>
          <Button
            size="icon"
            variant="secondary"
            onClick={handleDownloadPng}
            className="h-8 w-8 rounded-full flex items-center justify-center shrink-0"
            title="Download PNG"
          >
            <Download className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {visible && (
        <div
          className="rounded-3xl bg-secondary/30 p-4 overflow-x-auto flex justify-center custom-scrollbar border-0"
          dangerouslySetInnerHTML={{ __html: svgContent }}
        />
      )}
    </div>
  )
}
