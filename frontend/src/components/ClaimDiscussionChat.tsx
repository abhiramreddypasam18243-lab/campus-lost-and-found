import React, { useState } from 'react'

export interface ChatMessage {
  id: string
  senderRole: 'claimant' | 'moderator'
  senderAlias: string
  text: string
  timestamp: string
}

interface ClaimDiscussionChatProps {
  claimId: string
  itemTitle: string
  userRole: 'student' | 'moderator' | 'admin' | string
  onClose?: () => void
}

export const ClaimDiscussionChat: React.FC<ClaimDiscussionChatProps> = ({
  claimId,
  itemTitle,
  userRole,
  onClose,
}) => {
  const isModeratorOrAdmin = userRole === 'moderator' || userRole === 'admin'

  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: 'msg-1',
      senderRole: 'moderator',
      senderAlias: 'Desk Moderator #M12',
      text: 'Hello, your claim on this item is under review. Please confirm if there are any specific engravings or stickers on the back.',
      timestamp: 'Today at 09:15 AM',
    },
    {
      id: 'msg-2',
      senderRole: 'claimant',
      senderAlias: 'Claimant #C482',
      text: 'Yes! There is a small silver star sticker on the lower bottom right corner.',
      timestamp: 'Today at 09:20 AM',
    },
    {
      id: 'msg-3',
      senderRole: 'moderator',
      senderAlias: 'Desk Moderator #M12',
      text: 'Thank you! The physical verification matches. Your claim is approved and a handover passcode has been generated.',
      timestamp: 'Today at 09:25 AM',
    },
  ])

  const [inputText, setInputText] = useState<string>('')
  const [piiError, setPiiError] = useState<string | null>(null)

  const handleSendMessage = (e: React.FormEvent) => {
    e.preventDefault()
    setPiiError(null)

    const trimmed = inputText.trim()
    if (!trimmed) return

    // PII Scanner Shield (AC-27)
    const piiRegex = /\b(\d{3}-\d{2}-\d{4}|\d{10}|[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})\b/
    if (piiRegex.test(trimmed)) {
      setPiiError('PII Shield Alert: Phone numbers, emails, and student ID numbers cannot be shared in chat.')
      return
    }

    const newMessage: ChatMessage = {
      id: `msg-${Date.now()}`,
      senderRole: isModeratorOrAdmin ? 'moderator' : 'claimant',
      senderAlias: isModeratorOrAdmin ? 'Desk Moderator #M12' : 'Claimant #C482',
      text: trimmed,
      timestamp: 'Just now',
    }

    setMessages((prev) => [...prev, newMessage])
    setInputText('')
  }

  return (
    <div className="chat-modal-backdrop" onClick={onClose} role="dialog" aria-modal="true">
      <div className="chat-modal-window" onClick={(e) => e.stopPropagation()}>
        <div className="chat-modal-header">
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              <span className="secure-lock-icon">🔒</span>
              <h3 style={{ margin: 0, fontSize: '1.05rem', color: '#fff' }}>
                Secure Anonymous Claim Dialogue
              </h3>
            </div>
            <p style={{ margin: '0.2rem 0 0 0', fontSize: '0.78rem', color: 'var(--text-secondary)' }}>
              Item: <strong>{itemTitle}</strong> • Claim Ref: {claimId}
            </p>
          </div>
          {onClose && (
            <button className="modal-close" onClick={onClose} aria-label="Close Chat">
              ✕
            </button>
          )}
        </div>

        <div className="chat-privacy-banner">
          <span>🛡️ <strong>Identity Shield:</strong> Real names and student IDs are masked. Messages are securely logged in the audit trail.</span>
        </div>

        <div className="chat-messages-container">
          {messages.map((m) => {
            const isMe =
              (isModeratorOrAdmin && m.senderRole === 'moderator') ||
              (!isModeratorOrAdmin && m.senderRole === 'claimant')

            return (
              <div key={m.id} className={`chat-message-row ${isMe ? 'outgoing' : 'incoming'}`}>
                <div className="chat-bubble">
                  <div className="chat-sender-tag">
                    <span>{m.senderAlias}</span>
                    <small>{m.timestamp}</small>
                  </div>
                  <p className="chat-text">{m.text}</p>
                </div>
              </div>
            )
          })}
        </div>

        <form onSubmit={handleSendMessage} className="chat-input-bar">
          {piiError && <div className="chat-pii-error">{piiError}</div>}
          <div className="chat-input-row">
            <input
              type="text"
              className="chat-text-input"
              placeholder="Type an anonymous clarification message..."
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              required
            />
            <button type="submit" className="btn btn-primary btn-sm">
              Send ✈️
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
