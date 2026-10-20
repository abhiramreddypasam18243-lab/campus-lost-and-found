import React, { useEffect, useRef, useState, useCallback } from 'react'

export interface RedactionRegion {
  id: string
  x: number
  y: number
  width: number
  height: number
  label: string
  type: 'face' | 'text' | 'card' | 'custom'
  enabled: boolean
}

export type RedactionMode = 'blur' | 'pixelate' | 'blackout'

interface PrivacyRedactionStudioProps {
  initialImageUrl?: string | null
  onApplyRedactedPhoto: (file: File, dataUrl: string, regionsCount: number) => void
  onClose: () => void
}

export const PrivacyRedactionStudio: React.FC<PrivacyRedactionStudioProps> = ({
  initialImageUrl,
  onApplyRedactedPhoto,
  onClose,
}) => {
  const [imageSrc, setImageSrc] = useState<string | null>(initialImageUrl || null)
  const [regions, setRegions] = useState<RedactionRegion[]>([])
  const [redactionMode, setRedactionMode] = useState<RedactionMode>('pixelate')
  const [intensity, setIntensity] = useState<number>(14)
  const [isScanning, setIsScanning] = useState<boolean>(false)
  const [showOriginal, setShowOriginal] = useState<boolean>(false)
  const [customDrawing, setCustomDrawing] = useState<boolean>(false)

  // Drag-to-add region state
  const [isDragging, setIsDragging] = useState<boolean>(false)
  const [dragStart, setDragStart] = useState<{ x: number; y: number } | null>(null)
  const [dragCurrent, setDragCurrent] = useState<{ x: number; y: number } | null>(null)

  const displayCanvasRef = useRef<HTMLCanvasElement | null>(null)
  const imageElementRef = useRef<HTMLImageElement | null>(null)

  // Load preset demo cards for instant viva demonstration
  const loadDemoPreset = (preset: 'student_id' | 'wallet' | 'laptop') => {
    const canvas = document.createElement('canvas')
    const ctx = canvas.getContext('2d')
    if (!ctx) return

    canvas.width = 640
    canvas.height = 400

    if (preset === 'student_id') {
      // 1. Campus ID Card Background
      const grad = ctx.createLinearGradient(0, 0, 640, 400)
      grad.addColorStop(0, '#1e293b')
      grad.addColorStop(1, '#0f172a')
      ctx.fillStyle = grad
      ctx.fillRect(0, 0, 640, 400)

      // Card Base
      ctx.fillStyle = '#f8fafc'
      ctx.beginPath()
      ctx.roundRect(80, 40, 480, 320, 16)
      ctx.fill()
      ctx.lineWidth = 3
      ctx.strokeStyle = '#cbd5e1'
      ctx.stroke()

      // Header Bar
      ctx.fillStyle = '#1e40af'
      ctx.beginPath()
      ctx.roundRect(80, 40, 480, 64, [16, 16, 0, 0])
      ctx.fill()

      ctx.fillStyle = '#ffffff'
      ctx.font = 'bold 18px "Plus Jakarta Sans", sans-serif'
      ctx.fillText('CAMPUS TECHNICAL INSTITUTE', 110, 80)
      ctx.font = '11px sans-serif'
      ctx.fillStyle = '#93c5fd'
      ctx.fillText('STUDENT IDENTIFICATION SMART CARD', 110, 96)

      // Photo Portrait with realistic skin-tone representation
      ctx.fillStyle = '#e2e8f0'
      ctx.fillRect(110, 130, 110, 140)
      ctx.strokeStyle = '#94a3b8'
      ctx.strokeRect(110, 130, 110, 140)

      // Face silhouette with skin locus tones (R:210, G:160, B:140)
      ctx.fillStyle = 'rgb(215, 165, 140)'
      ctx.beginPath()
      ctx.ellipse(165, 190, 36, 46, 0, 0, Math.PI * 2)
      ctx.fill()
      // Hair
      ctx.fillStyle = '#262626'
      ctx.beginPath()
      ctx.arc(165, 170, 38, Math.PI * 0.9, Math.PI * 2.1)
      ctx.fill()
      // Shoulders
      ctx.fillStyle = '#3b82f6'
      ctx.beginPath()
      ctx.ellipse(165, 270, 45, 30, 0, Math.PI, 0)
      ctx.fill()

      // Text Fields (Student details)
      ctx.fillStyle = '#0f172a'
      ctx.font = 'bold 16px sans-serif'
      ctx.fillText('NAME: AARAV SHARMA', 240, 160)
      ctx.font = '13px sans-serif'
      ctx.fillStyle = '#334155'
      ctx.fillText('ROLL NO: 2024-AIDS-0428', 240, 190)
      ctx.fillText('DEPT: ARTIFICIAL INTELLIGENCE & DS', 240, 215)
      ctx.fillText('DOB: 14-MAY-2003   BLOOD: O+VE', 240, 240)
      ctx.fillText('VALID THRU: 06/2028', 240, 265)

      // Barcode strip
      ctx.fillStyle = '#1e293b'
      for (let i = 240; i < 520; i += 6) {
        const w = (i % 12 === 0) ? 3 : ((i % 18 === 0) ? 4 : 2)
        ctx.fillRect(i, 290, w, 32)
      }
    } else if (preset === 'wallet') {
      // Leather Wallet Texture
      ctx.fillStyle = '#3b2219'
      ctx.fillRect(0, 0, 640, 400)

      // Wallet leather folds
      ctx.fillStyle = '#543324'
      ctx.beginPath()
      ctx.roundRect(100, 60, 440, 280, 20)
      ctx.fill()
      ctx.strokeStyle = '#27140e'
      ctx.lineWidth = 4
      ctx.stroke()

      // Card insert slot with driver license / card
      ctx.fillStyle = '#f1f5f9'
      ctx.fillRect(140, 100, 360, 200)

      // Portrait photo
      ctx.fillStyle = 'rgb(220, 170, 145)'
      ctx.beginPath()
      ctx.ellipse(200, 180, 34, 44, 0, 0, Math.PI * 2)
      ctx.fill()
      ctx.fillStyle = '#171717'
      ctx.beginPath()
      ctx.arc(200, 160, 36, Math.PI, 0)
      ctx.fill()

      // License text
      ctx.fillStyle = '#0f172a'
      ctx.font = 'bold 14px sans-serif'
      ctx.fillText('STATE DRIVER LICENSE', 260, 135)
      ctx.font = '12px sans-serif'
      ctx.fillStyle = '#dc2626'
      ctx.fillText('LIC NO: DL-8842-99014X', 260, 165)
      ctx.fillStyle = '#334155'
      ctx.fillText('EXP: 10/2030  CLASS: LMV', 260, 190)
      ctx.fillText('ADDR: 402 NORTH CAMPUS RD', 260, 215)
    } else {
      // Laptop with sticker and webcam
      ctx.fillStyle = '#1e293b'
      ctx.fillRect(0, 0, 640, 400)

      // Laptop lid
      ctx.fillStyle = '#334155'
      ctx.beginPath()
      ctx.roundRect(120, 50, 400, 300, 12)
      ctx.fill()
      ctx.strokeStyle = '#64748b'
      ctx.lineWidth = 2
      ctx.stroke()

      // Apple / Campus center logo
      ctx.fillStyle = '#94a3b8'
      ctx.beginPath()
      ctx.arc(320, 190, 28, 0, Math.PI * 2)
      ctx.fill()

      // Webcam at top
      ctx.fillStyle = '#0f172a'
      ctx.beginPath()
      ctx.arc(320, 64, 4, 0, Math.PI * 2)
      ctx.fill()

      // Personal phone sticker on bottom right
      ctx.fillStyle = '#fef08a'
      ctx.fillRect(360, 250, 140, 70)
      ctx.strokeStyle = '#ca8a04'
      ctx.strokeRect(360, 250, 140, 70)

      ctx.fillStyle = '#854d0e'
      ctx.font = 'bold 10px sans-serif'
      ctx.fillText('PROPERTY OF ABHIRAM', 370, 275)
      ctx.font = '11px sans-serif'
      ctx.fillStyle = '#b91c1c'
      ctx.fillText('CELL: +91 98765-43210', 370, 295)
    }

    const dataUrl = canvas.toDataURL('image/jpeg', 0.92)
    setImageSrc(dataUrl)
  }

  // Auto-run Computer Vision detector when image changes
  useEffect(() => {
    if (!imageSrc) return

    const img = new Image()
    img.crossOrigin = 'anonymous'
    img.src = imageSrc
    img.onload = () => {
      imageElementRef.current = img
      runComputerVisionPrivacyScan(img)
    }
  }, [imageSrc])

  // Fast client-side Computer Vision scan using HTML5 Canvas & pixel raster inspection
  const runComputerVisionPrivacyScan = (img: HTMLImageElement) => {
    setIsScanning(true)

    // Store original image dimensions
    const w = img.width
    const h = img.height

    const scanCanvas = document.createElement('canvas')
    const ctx = scanCanvas.getContext('2d')
    if (!ctx) {
      setIsScanning(false)
      return
    }

    scanCanvas.width = w
    scanCanvas.height = h
    ctx.drawImage(img, 0, 0, w, h)

    const imageData = ctx.getImageData(0, 0, w, h)
    const data = imageData.data

    const detected: RedactionRegion[] = []

    // 1. Skin Locus Detector (YCbCr + Normalized RGB Skin Segmentation)
    // Divides image into 24x24 blocks to cluster facial candidates
    const blockSize = Math.max(16, Math.floor(Math.min(w, h) / 25))
    const cols = Math.floor(w / blockSize)
    const rows = Math.floor(h / blockSize)
    const skinGrid: boolean[][] = Array.from({ length: rows }, () => Array(cols).fill(false))

    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        let skinPixels = 0
        let total = 0
        const startX = c * blockSize
        const startY = r * blockSize

        for (let py = 0; py < blockSize; py += 3) {
          for (let px = 0; px < blockSize; px += 3) {
            const idx = ((startY + py) * w + (startX + px)) * 4
            const red = data[idx]
            const green = data[idx + 1]
            const blue = data[idx + 2]

            // Kovac / Peer & Solina skin locus rule
            const isSkin =
              red > 95 &&
              green > 40 &&
              blue > 20 &&
              Math.max(red, green, blue) - Math.min(red, green, blue) > 15 &&
              Math.abs(red - green) > 15 &&
              red > green &&
              red > blue

            if (isSkin) skinPixels++
            total++
          }
        }

        // If block has > 40% skin locus pixels
        if (total > 0 && skinPixels / total > 0.4) {
          skinGrid[r][c] = true
        }
      }
    }

    // Cluster contiguous skin blocks into face bounding boxes
    const visited: boolean[][] = Array.from({ length: rows }, () => Array(cols).fill(false))
    for (let r = 0; r < rows; r++) {
      for (let c = 0; c < cols; c++) {
        if (skinGrid[r][c] && !visited[r][c]) {
          // BFS flood fill
          let minR = r,
            maxR = r,
            minC = c,
            maxC = c
          let count = 0
          const queue: [number, number][] = [[r, c]]
          visited[r][c] = true

          while (queue.length > 0) {
            const [currR, currC] = queue.shift()!
            count++
            minR = Math.min(minR, currR)
            maxR = Math.max(maxR, currR)
            minC = Math.min(minC, currC)
            maxC = Math.max(maxC, currC)

            const neighbors: [number, number][] = [
              [currR - 1, currC],
              [currR + 1, currC],
              [currR, currC - 1],
              [currR, currC + 1],
            ]
            for (const [nr, nc] of neighbors) {
              if (
                nr >= 0 &&
                nr < rows &&
                nc >= 0 &&
                nc < cols &&
                skinGrid[nr][nc] &&
                !visited[nr][nc]
              ) {
                visited[nr][nc] = true
                queue.push([nr, nc])
              }
            }
          }

          const boxW = (maxC - minC + 1) * blockSize
          const boxH = (maxR - minR + 1) * blockSize
          const aspect = boxH / boxW

          // Human face oval aspect ratio check (0.8 <= H/W <= 2.2) and minimum cluster size
          if (count >= 2 && count <= 40 && aspect >= 0.75 && aspect <= 2.2) {
            // Expand box slightly around hair/head
            const padX = Math.round(boxW * 0.15)
            const padY = Math.round(boxH * 0.2)
            const fx = Math.max(0, minC * blockSize - padX)
            const fy = Math.max(0, minR * blockSize - padY)
            const fw = Math.min(w - fx, boxW + padX * 2)
            const fh = Math.min(h - fy, boxH + padY * 2)

            detected.push({
              id: `face-${detected.length + 1}`,
              x: fx,
              y: fy,
              width: fw,
              height: fh,
              label: '👤 Face / Portrait Photo',
              type: 'face',
              enabled: true,
            })
          }
        }
      }
    }

    // 2. High-Frequency Text & Number-Plate Edge Detector
    // Alphanumeric characters (roll numbers, credit cards) generate dense horizontal edge transitions
    const textBandHeight = Math.max(20, Math.floor(h / 18))
    const textBandWidth = Math.max(40, Math.floor(w / 10))
    const tCols = Math.floor(w / textBandWidth)
    const tRows = Math.floor(h / textBandHeight)

    for (let tr = 0; tr < tRows; tr++) {
      for (let tc = 0; tc < tCols; tc++) {
        const sx = tc * textBandWidth
        const sy = tr * textBandHeight
        let transitions = 0
        let samples = 0

        // Scan middle horizontal lines of this band
        for (let py = Math.floor(textBandHeight * 0.3); py <= Math.floor(textBandHeight * 0.7); py += 4) {
          let prevLum = -1
          for (let px = 2; px < textBandWidth - 2; px += 2) {
            const idx = ((sy + py) * w + (sx + px)) * 4
            const lum = 0.299 * data[idx] + 0.587 * data[idx + 1] + 0.114 * data[idx + 2]
            if (prevLum >= 0 && Math.abs(lum - prevLum) > 55) {
              transitions++
            }
            prevLum = lum
            samples++
          }
        }

        // High transition density indicates printed text / digits / barcodes
        if (samples > 0 && transitions / samples > 0.28) {
          // Avoid overlapping existing face detections
          const overlap = detected.some(
            (d) =>
              sx < d.x + d.width &&
              sx + textBandWidth > d.x &&
              sy < d.y + d.height &&
              sy + textBandHeight > d.y
          )

          if (!overlap) {
            detected.push({
              id: `text-${detected.length + 1}`,
              x: sx,
              y: sy,
              width: textBandWidth,
              height: textBandHeight,
              label: '💳 ID Number / Card Text',
              type: 'text',
              enabled: true,
            })
          }
        }
      }
    }

    // Merge adjacent text boxes horizontally to form single clean text banners
    const merged: RedactionRegion[] = []
    const faceBoxes = detected.filter((d) => d.type === 'face')
    const textBoxes = detected.filter((d) => d.type === 'text')

    merged.push(...faceBoxes)

    const usedText = new Set<string>()
    for (let i = 0; i < textBoxes.length; i++) {
      const b1 = textBoxes[i]
      if (usedText.has(b1.id)) continue

      const curX = b1.x
      const curY = b1.y
      let curW = b1.width
      let curH = b1.height
      usedText.add(b1.id)

      for (let j = i + 1; j < textBoxes.length; j++) {
        const b2 = textBoxes[j]
        if (usedText.has(b2.id)) continue

        // If on same line and horizontally adjacent/touching
        if (Math.abs(b1.y - b2.y) < b1.height * 0.5 && Math.abs(curX + curW - b2.x) <= b1.width * 0.4) {
          curW = Math.max(curX + curW, b2.x + b2.width) - curX
          curH = Math.max(curH, b2.height)
          usedText.add(b2.id)
        }
      }

      merged.push({
        id: `text-merged-${i}`,
        x: curX,
        y: curY,
        width: curW,
        height: curH,
        label: '💳 ID Roll No / Sensitive Text',
        type: 'text',
        enabled: true,
      })
    }

    setTimeout(() => {
      setRegions(merged)
      setIsScanning(false)
    }, 450)
  }

  // Redraw canvas whenever regions, mode, intensity, or image changes
  const renderCanvas = useCallback(() => {
    const canvas = displayCanvasRef.current
    const img = imageElementRef.current
    if (!canvas || !img) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    canvas.width = img.width
    canvas.height = img.height

    // Draw base original photo
    ctx.drawImage(img, 0, 0, img.width, img.height)

    if (showOriginal) {
      // Just showing original clean photo
      return
    }

    // Apply Redactions on active regions
    regions.forEach((region) => {
      if (!region.enabled) return

      const rx = Math.max(0, Math.floor(region.x))
      const ry = Math.max(0, Math.floor(region.y))
      const rw = Math.min(canvas.width - rx, Math.floor(region.width))
      const rh = Math.min(canvas.height - ry, Math.floor(region.height))

      if (rw <= 0 || rh <= 0) return

      if (redactionMode === 'pixelate') {
        // Mosaic Pixelation
        const block = Math.max(8, intensity)
        const subCanvas = document.createElement('canvas')
        const subCtx = subCanvas.getContext('2d')
        if (subCtx) {
          const smallW = Math.max(1, Math.floor(rw / block))
          const smallH = Math.max(1, Math.floor(rh / block))
          subCanvas.width = smallW
          subCanvas.height = smallH

          subCtx.drawImage(img, rx, ry, rw, rh, 0, 0, smallW, smallH)
          ctx.imageSmoothingEnabled = false
          ctx.drawImage(subCanvas, 0, 0, smallW, smallH, rx, ry, rw, rh)
          ctx.imageSmoothingEnabled = true
        }
      } else if (redactionMode === 'blur') {
        // Frosted Gaussian Blur
        ctx.save()
        ctx.beginPath()
        ctx.rect(rx, ry, rw, rh)
        ctx.clip()
        ctx.filter = `blur(${Math.max(8, intensity)}px)`
        ctx.drawImage(img, 0, 0)
        ctx.restore()
      } else if (redactionMode === 'blackout') {
        // Security Blackout Banner
        ctx.fillStyle = '#090d16'
        ctx.fillRect(rx, ry, rw, rh)

        // Diagonal security stripes
        ctx.strokeStyle = 'rgba(239, 68, 68, 0.4)'
        ctx.lineWidth = 2
        for (let x = rx - rh; x < rx + rw; x += 14) {
          ctx.beginPath()
          ctx.moveTo(x, ry)
          ctx.lineTo(x + rh, ry + rh)
          ctx.stroke()
        }

        // Stencil security stamp
        ctx.fillStyle = '#f87171'
        ctx.font = `bold ${Math.max(10, Math.floor(rh * 0.45))}px "JetBrains Mono", monospace`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText('REDACTED', rx + rw / 2, ry + rh / 2)
      }

      // Draw bounding box outlines & badges (subtle cyan/amber glow)
      ctx.lineWidth = 2
      ctx.strokeStyle =
        region.type === 'face'
          ? 'rgba(56, 189, 248, 0.9)'
          : region.type === 'text'
          ? 'rgba(245, 158, 11, 0.9)'
          : 'rgba(168, 85, 247, 0.9)'
      ctx.setLineDash([6, 4])
      ctx.strokeRect(rx, ry, rw, rh)
      ctx.setLineDash([])
    })

    // Draw active user drag box if currently dragging
    if (isDragging && dragStart && dragCurrent) {
      const dx = Math.min(dragStart.x, dragCurrent.x)
      const dy = Math.min(dragStart.y, dragCurrent.y)
      const dw = Math.abs(dragCurrent.x - dragStart.x)
      const dh = Math.abs(dragCurrent.y - dragStart.y)

      ctx.lineWidth = 2
      ctx.strokeStyle = '#a855f7'
      ctx.setLineDash([4, 4])
      ctx.fillStyle = 'rgba(168, 85, 247, 0.25)'
      ctx.fillRect(dx, dy, dw, dh)
      ctx.strokeRect(dx, dy, dw, dh)
      ctx.setLineDash([])
    }
  }, [regions, redactionMode, intensity, showOriginal, isDragging, dragStart, dragCurrent])

  useEffect(() => {
    renderCanvas()
  }, [renderCanvas])

  // Mouse / Touch handlers for manual custom redaction drawing
  const getCanvasCoordinates = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const canvas = displayCanvasRef.current
    if (!canvas) return { x: 0, y: 0 }
    const rect = canvas.getBoundingClientRect()
    const scaleX = canvas.width / rect.width
    const scaleY = canvas.height / rect.height
    return {
      x: (e.clientX - rect.left) * scaleX,
      y: (e.clientY - rect.top) * scaleY,
    }
  }

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!customDrawing) return
    const pos = getCanvasCoordinates(e)
    setIsDragging(true)
    setDragStart(pos)
    setDragCurrent(pos)
  }

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (!isDragging) return
    const pos = getCanvasCoordinates(e)
    setDragCurrent(pos)
  }

  const handleMouseUp = () => {
    if (isDragging && dragStart && dragCurrent) {
      const x = Math.min(dragStart.x, dragCurrent.x)
      const y = Math.min(dragStart.y, dragCurrent.y)
      const width = Math.abs(dragCurrent.x - dragStart.x)
      const height = Math.abs(dragCurrent.y - dragStart.y)

      // Only save if box has noticeable size
      if (width > 12 && height > 12) {
        setRegions((prev) => [
          ...prev,
          {
            id: `custom-${Date.now()}`,
            x,
            y,
            width,
            height,
            label: '✏️ Custom Redacted Area',
            type: 'custom',
            enabled: true,
          },
        ])
      }
    }
    setIsDragging(false)
    setDragStart(null)
    setDragCurrent(null)
  }

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return

    const reader = new FileReader()
    reader.onload = (event) => {
      setImageSrc(event.target?.result as string)
    }
    reader.readAsDataURL(file)
  }

  // Toggle region state
  const toggleRegion = (id: string) => {
    setRegions((prev) =>
      prev.map((r) => (r.id === id ? { ...r, enabled: !r.enabled } : r))
    )
  }

  // Delete region
  const removeRegion = (id: string) => {
    setRegions((prev) => prev.filter((r) => r.id !== id))
  }

  // Final export of sanitized photo
  const handleApply = () => {
    const canvas = displayCanvasRef.current
    if (!canvas) return

    // Re-render without boundary boxes for clean export
    const exportCanvas = document.createElement('canvas')
    const img = imageElementRef.current
    if (!img) return

    exportCanvas.width = img.width
    exportCanvas.height = img.height
    const ctx = exportCanvas.getContext('2d')
    if (!ctx) return

    ctx.drawImage(img, 0, 0)

    regions.forEach((region) => {
      if (!region.enabled) return
      const rx = Math.max(0, Math.floor(region.x))
      const ry = Math.max(0, Math.floor(region.y))
      const rw = Math.min(exportCanvas.width - rx, Math.floor(region.width))
      const rh = Math.min(exportCanvas.height - ry, Math.floor(region.height))

      if (rw <= 0 || rh <= 0) return

      if (redactionMode === 'pixelate') {
        const block = Math.max(8, intensity)
        const subCanvas = document.createElement('canvas')
        const subCtx = subCanvas.getContext('2d')
        if (subCtx) {
          const smallW = Math.max(1, Math.floor(rw / block))
          const smallH = Math.max(1, Math.floor(rh / block))
          subCanvas.width = smallW
          subCanvas.height = smallH
          subCtx.drawImage(img, rx, ry, rw, rh, 0, 0, smallW, smallH)
          ctx.imageSmoothingEnabled = false
          ctx.drawImage(subCanvas, 0, 0, smallW, smallH, rx, ry, rw, rh)
          ctx.imageSmoothingEnabled = true
        }
      } else if (redactionMode === 'blur') {
        ctx.save()
        ctx.beginPath()
        ctx.rect(rx, ry, rw, rh)
        ctx.clip()
        ctx.filter = `blur(${Math.max(8, intensity)}px)`
        ctx.drawImage(img, 0, 0)
        ctx.restore()
      } else {
        ctx.fillStyle = '#090d16'
        ctx.fillRect(rx, ry, rw, rh)
        ctx.fillStyle = '#f87171'
        ctx.font = `bold ${Math.max(10, Math.floor(rh * 0.45))}px "JetBrains Mono", monospace`
        ctx.textAlign = 'center'
        ctx.textBaseline = 'middle'
        ctx.fillText('REDACTED', rx + rw / 2, ry + rh / 2)
      }
    })

    exportCanvas.toBlob(
      (blob) => {
        if (!blob) return
        const sanitizedFile = new File([blob], 'sanitized_campus_item.jpg', {
          type: 'image/jpeg',
          lastModified: Date.now(),
        })
        const cleanDataUrl = exportCanvas.toDataURL('image/jpeg', 0.9)
        const activeCount = regions.filter((r) => r.enabled).length
        onApplyRedactedPhoto(sanitizedFile, cleanDataUrl, activeCount)
      },
      'image/jpeg',
      0.9
    )
  }

  const enabledCount = regions.filter((r) => r.enabled).length

  return (
    <div className="modal-overlay" style={{ zIndex: 1100 }}>
      <div
        className="modal-card"
        style={{
          maxWidth: '920px',
          width: '95%',
          maxHeight: '92vh',
          display: 'flex',
          flexDirection: 'column',
          padding: '1.5rem',
        }}
      >
        {/* Header */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            borderBottom: '1px solid var(--border-subtle)',
            paddingBottom: '1rem',
            marginBottom: '1rem',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <span style={{ fontSize: '1.6rem' }}>🕶️</span>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.2rem', color: '#fff' }}>
                Automated Face &amp; ID Privacy Redaction Studio
              </h3>
              <small style={{ color: 'var(--text-secondary)' }}>
                Computer Vision scanning: automatically blur faces, student IDs, card numbers, and roll numbers before public listing.
              </small>
            </div>
          </div>
          <button
            type="button"
            className="link-btn"
            style={{ fontSize: '1.2rem', padding: '0.25rem 0.5rem' }}
            onClick={onClose}
          >
            ✕
          </button>
        </div>

        {/* Demo Presets Row */}
        <div
          style={{
            display: 'flex',
            gap: '0.5rem',
            alignItems: 'center',
            flexWrap: 'wrap',
            background: 'rgba(15, 23, 42, 0.6)',
            padding: '0.6rem 0.85rem',
            borderRadius: 'var(--radius-sm)',
            border: '1px solid var(--border-subtle)',
            marginBottom: '1rem',
          }}
        >
          <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-secondary)' }}>
            ✨ Instant Demo Presets:
          </span>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            style={{ fontSize: '0.8rem', padding: '0.3rem 0.65rem' }}
            onClick={() => loadDemoPreset('student_id')}
          >
            🎓 Student ID Card
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            style={{ fontSize: '0.8rem', padding: '0.3rem 0.65rem' }}
            onClick={() => loadDemoPreset('wallet')}
          >
            💳 Found Wallet &amp; License
          </button>
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            style={{ fontSize: '0.8rem', padding: '0.3rem 0.65rem' }}
            onClick={() => loadDemoPreset('laptop')}
          >
            💻 Laptop with Contact Sticker
          </button>

          <label
            htmlFor="upload-custom-photo"
            className="btn btn-secondary btn-sm"
            style={{ fontSize: '0.8rem', padding: '0.3rem 0.65rem', marginLeft: 'auto', cursor: 'pointer' }}
          >
            📂 Upload Custom Photo
          </label>
          <input
            id="upload-custom-photo"
            type="file"
            accept="image/*"
            style={{ display: 'none' }}
            onChange={handleFileUpload}
          />
        </div>

        {/* Canvas & Controls Workspace */}
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'minmax(0, 1fr) 280px',
            gap: '1.25rem',
            overflowY: 'auto',
            paddingRight: '0.25rem',
            flex: 1,
          }}
        >
          {/* Main Visual Canvas Area */}
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              alignItems: 'center',
              justifyContent: 'center',
              background: '#030712',
              borderRadius: 'var(--radius-md)',
              border: '1px solid var(--border-subtle)',
              position: 'relative',
              overflow: 'hidden',
              minHeight: '340px',
            }}
          >
            {isScanning && (
              <div
                style={{
                  position: 'absolute',
                  top: 0,
                  left: 0,
                  right: 0,
                  bottom: 0,
                  background: 'rgba(3, 7, 18, 0.75)',
                  backdropFilter: 'blur(3px)',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  zIndex: 20,
                  gap: '0.75rem',
                }}
              >
                <div className="scanner-line" style={{ width: '80%', height: '3px' }} />
                <span style={{ fontSize: '0.9rem', color: '#38bdf8', fontWeight: 600 }}>
                  🔍 Computer Vision Scanning: Detecting faces, cards &amp; text strips...
                </span>
              </div>
            )}

            {imageSrc ? (
              <div style={{ position: 'relative', width: '100%', display: 'flex', justifyContent: 'center' }}>
                <canvas
                  ref={displayCanvasRef}
                  style={{
                    maxWidth: '100%',
                    maxHeight: '440px',
                    objectFit: 'contain',
                    cursor: customDrawing ? 'crosshair' : 'default',
                    borderRadius: 'var(--radius-sm)',
                  }}
                  onMouseDown={handleMouseDown}
                  onMouseMove={handleMouseMove}
                  onMouseUp={handleMouseUp}
                />
              </div>
            ) : (
              <div style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-muted)' }}>
                <span style={{ fontSize: '2.5rem', display: 'block', marginBottom: '0.5rem' }}>📷</span>
                <p>Select a demo preset above or upload an item photo to begin privacy redaction.</p>
              </div>
            )}

            {/* Quick compare toggle banner */}
            {imageSrc && (
              <div
                style={{
                  position: 'absolute',
                  bottom: '12px',
                  display: 'flex',
                  gap: '0.75rem',
                  background: 'rgba(17, 24, 39, 0.85)',
                  backdropFilter: 'blur(8px)',
                  padding: '0.35rem 0.75rem',
                  borderRadius: 'var(--radius-full)',
                  border: '1px solid var(--border-subtle)',
                }}
              >
                <button
                  type="button"
                  className="link-btn"
                  style={{
                    fontSize: '0.75rem',
                    color: showOriginal ? '#38bdf8' : 'var(--text-secondary)',
                  }}
                  onMouseDown={() => setShowOriginal(true)}
                  onMouseUp={() => setShowOriginal(false)}
                  onTouchStart={() => setShowOriginal(true)}
                  onTouchEnd={() => setShowOriginal(false)}
                >
                  👁️ {showOriginal ? 'Showing Original Photo' : 'Hold to View Original'}
                </button>
                <span style={{ color: 'var(--border-subtle)' }}>|</span>
                <span style={{ fontSize: '0.75rem', color: '#4ade80' }}>
                  ✓ {enabledCount} Privacy Zones Protected
                </span>
              </div>
            )}
          </div>

          {/* Right Control Sidebar */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {/* Redaction Style Selector */}
            <div className="card" style={{ padding: '0.85rem', background: 'rgba(17, 24, 39, 0.6)' }}>
              <label className="form-label" style={{ fontSize: '0.8rem', marginBottom: '0.4rem' }}>
                🛡️ Redaction Mode
              </label>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '0.4rem' }}>
                <button
                  type="button"
                  className={`btn btn-sm ${redactionMode === 'pixelate' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ padding: '0.4rem 0.2rem', fontSize: '0.75rem' }}
                  onClick={() => setRedactionMode('pixelate')}
                >
                  Mosaic
                </button>
                <button
                  type="button"
                  className={`btn btn-sm ${redactionMode === 'blur' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ padding: '0.4rem 0.2rem', fontSize: '0.75rem' }}
                  onClick={() => setRedactionMode('blur')}
                >
                  Blur
                </button>
                <button
                  type="button"
                  className={`btn btn-sm ${redactionMode === 'blackout' ? 'btn-primary' : 'btn-secondary'}`}
                  style={{ padding: '0.4rem 0.2rem', fontSize: '0.75rem' }}
                  onClick={() => setRedactionMode('blackout')}
                >
                  Blackout
                </button>
              </div>

              {/* Blur Intensity Slider */}
              {redactionMode !== 'blackout' && (
                <div style={{ marginTop: '0.75rem' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                    <span>Blur Strength:</span>
                    <span>{intensity}px</span>
                  </div>
                  <input
                    type="range"
                    min="8"
                    max="28"
                    step="2"
                    value={intensity}
                    onChange={(e) => setIntensity(Number(e.target.value))}
                    style={{ width: '100%', marginTop: '0.25rem', accentColor: 'var(--accent-blue)' }}
                  />
                </div>
              )}
            </div>

            {/* Manual Draw Zone Button */}
            <button
              type="button"
              className={`btn ${customDrawing ? 'btn-primary' : 'btn-secondary'} btn-sm`}
              style={{ width: '100%', fontSize: '0.8rem' }}
              onClick={() => setCustomDrawing(!customDrawing)}
            >
              {customDrawing ? '✓ Drawing Active (Drag on photo)' : '✏️ Draw Custom Redaction Box'}
            </button>

            {/* Detected Privacy Regions List */}
            <div
              className="card"
              style={{
                padding: '0.85rem',
                background: 'rgba(17, 24, 39, 0.6)',
                flex: 1,
                display: 'flex',
                flexDirection: 'column',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <span style={{ fontSize: '0.8rem', fontWeight: 600 }}>Detected Regions ({regions.length})</span>
                {regions.length > 0 && (
                  <button
                    type="button"
                    className="link-btn"
                    style={{ fontSize: '0.7rem' }}
                    onClick={() =>
                      setRegions((prev) => prev.map((r) => ({ ...r, enabled: !prev.every((p) => p.enabled) })))
                    }
                  >
                    Toggle All
                  </button>
                )}
              </div>

              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', overflowY: 'auto', maxHeight: '180px' }}>
                {regions.length === 0 ? (
                  <small style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '1rem 0' }}>
                    No sensitive regions detected yet.
                  </small>
                ) : (
                  regions.map((reg) => (
                    <div
                      key={reg.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '0.35rem 0.5rem',
                        background: reg.enabled ? 'rgba(30, 41, 59, 0.7)' : 'rgba(15, 23, 42, 0.4)',
                        borderRadius: 'var(--radius-sm)',
                        border: '1px solid',
                        borderColor: reg.enabled ? 'var(--border-accent)' : 'var(--border-subtle)',
                        fontSize: '0.75rem',
                      }}
                    >
                      <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', cursor: 'pointer', overflow: 'hidden' }}>
                        <input
                          type="checkbox"
                          checked={reg.enabled}
                          onChange={() => toggleRegion(reg.id)}
                          style={{ accentColor: 'var(--accent-blue)' }}
                        />
                        <span style={{ whiteSpace: 'nowrap', textOverflow: 'ellipsis', overflow: 'hidden' }}>
                          {reg.label}
                        </span>
                      </label>
                      <button
                        type="button"
                        className="link-btn"
                        style={{ color: 'var(--accent-rose)', padding: '0 0.25rem' }}
                        onClick={() => removeRegion(reg.id)}
                        title="Remove region"
                      >
                        ✕
                      </button>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        </div>

        {/* Footer actions */}
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            marginTop: '1.25rem',
            paddingTop: '0.85rem',
            borderTop: '1px solid var(--border-subtle)',
          }}
        >
          <button type="button" className="btn btn-secondary" onClick={onClose}>
            Cancel
          </button>
          <div style={{ display: 'flex', gap: '0.75rem' }}>
            <button
              type="button"
              className="btn btn-primary"
              disabled={!imageSrc || enabledCount === 0}
              onClick={handleApply}
            >
              🛡️ Apply &amp; Attach Redacted Photo ({enabledCount} Blurred)
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}
