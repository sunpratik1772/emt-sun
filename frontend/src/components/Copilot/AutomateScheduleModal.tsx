import { useState } from 'react'
import Modal from '../Modal'
import { Button } from '../ui/Button'

type AutomateScheduleModalProps = {
  onCancel: () => void
  onConfirm: (scheduleDetail: string) => void
}

export default function AutomateScheduleModal({ onCancel, onConfirm }: AutomateScheduleModalProps) {
  const [value, setValue] = useState('')

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const trimmed = value.trim()
    if (!trimmed) return
    onConfirm(trimmed)
  }

  return (
    <Modal ariaLabel="Automation schedule" onClose={onCancel} zIndex={200}>
      <form
        onSubmit={handleSubmit}
        style={{ padding: 20, width: 'min(420px, 92vw)', display: 'grid', gap: 12 }}
      >
        <h3 style={{ margin: 0, fontSize: 14, fontWeight: 600, color: 'var(--text-0)' }}>
          When should this run?
        </h3>
        <p style={{ margin: 0, fontSize: 12, lineHeight: 1.5, color: 'var(--text-2)' }}>
          Describe the schedule — for example weekdays at 9am, every 30 minutes for 2 hours, or daily at 6pm UTC.
        </p>
        <input
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="e.g. every weekday at 9:00 AM"
          autoFocus
          className="rounded-lg px-3 py-2 outline-none"
          style={{
            fontSize: 12,
            background: 'var(--bg-2)',
            color: 'var(--text-0)',
            border: '1px solid var(--border)',
          }}
        />
        <div className="flex gap-2 justify-end">
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" disabled={!value.trim()}>
            Continue
          </Button>
        </div>
      </form>
    </Modal>
  )
}
