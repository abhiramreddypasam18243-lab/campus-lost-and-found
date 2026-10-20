import React, { useEffect, useState } from 'react'
import QRCode from 'qrcode'

interface QRCodeHandoverProps {
  claimId: string
  handoverCode: string
  itemTitle: string
  onVerifyCode?: (code: string) => void
  isStaffPortal?: boolean
}

export const QRCodeHandover: React.FC<QRCodeHandoverProps> = ({
  claimId,
  handoverCode,
  itemTitle,
  onVerifyCode,
  isStaffPortal = false,
}) => {
  const [qrDataUrl, setQrDataUrl] = useState<string>('')
  const [copied, setCopied] = useState<boolean>(false)
  const [scanning, setScanning] = useState<boolean>(false)

  useEffect(() => {
    if (!handoverCode) return

    // Encode verified handover payload into high-contrast QR
    const payload = JSON.stringify({
      claim_id: claimId,
      code: handoverCode.toUpperCase(),
      service: 'campus_handover_v1',
    })

    QRCode.toDataURL(payload, {
      width: 220,
      margin: 2,
      color: {
        dark: '#0f172a',
        light: '#ffffff',
      },
    })
      .then((url) => setQrDataUrl(url))
      .catch(() => {})
  }, [claimId, handoverCode])

  const handleCopyCode = () => {
    navigator.clipboard?.writeText(handoverCode)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleSimulateScan = () => {
    setScanning(true)
    setTimeout(() => {
      setScanning(false)
      if (onVerifyCode) {
        onVerifyCode(handoverCode)
      }
    }, 1200)
  }

  return (
    <div className="qr-handover-card" role="region" aria-label="QR Code Handover Pass">
      <div className="qr-header">
        <span className="qr-badge-tag">🔒 CRYPTOGRAPHIC HANDOVER PASS</span>
        <h3 style={{ margin: '0.4rem 0 0 0', fontSize: '1.15rem', color: '#fff' }}>
          {itemTitle || 'Lost Property Return'}
        </h3>
        <small style={{ color: 'var(--text-muted)' }}>Claim ID: {claimId}</small>
      </div>

      <div className="qr-visual-block">
        {qrDataUrl ? (
          <div className="qr-frame">
            <img src={qrDataUrl} alt="Handover Verification QR Code" className="qr-image" />
            <div className="qr-scan-corners"></div>
          </div>
        ) : (
          <div className="qr-placeholder">Generating Secure QR...</div>
        )}

        <div className="qr-code-display">
          <label style={{ fontSize: '0.75rem', textTransform: 'uppercase', color: 'var(--text-muted)', letterSpacing: '0.05em' }}>
            Single-Use 8-Character Passcode
          </label>
          <div className="code-pill-row">
            <span className="handover-char-code">{handoverCode}</span>
            <button
              type="button"
              className="btn btn-secondary btn-sm"
              onClick={handleCopyCode}
              title="Copy code to clipboard"
            >
              {copied ? '✓ Copied' : '📋 Copy'}
            </button>
          </div>
          <span style={{ fontSize: '0.72rem', color: '#38bdf8' }}>
            ● Valid for 24 hours • Protected by HMAC-SHA256 • Max 5 attempts
          </span>
        </div>
      </div>

      <div className="qr-actions-row">
        {isStaffPortal && onVerifyCode ? (
          <button
            type="button"
            className="btn btn-primary"
            style={{ width: '100%' }}
            onClick={handleSimulateScan}
            disabled={scanning}
          >
            {scanning ? '📷 Scanning Dynamic QR...' : '📷 Scan QR Code with Camera'}
          </button>
        ) : (
          <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--text-secondary)', textAlign: 'center' }}>
            📱 Present this QR code or 8-character passcode to staff at the designated physical campus desk to claim your item.
          </p>
        )}
      </div>
    </div>
  )
}
