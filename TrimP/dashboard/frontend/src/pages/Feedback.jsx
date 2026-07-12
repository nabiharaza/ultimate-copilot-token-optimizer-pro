import { ArrowLeft, CheckCircle2, MessageSquare, Send } from 'lucide-react'
import { useState } from 'react'

export default function Feedback({ onNavigate }) {
  const [message, setMessage] = useState('')
  const [sent, setSent] = useState(false)

  function submit(event) {
    event.preventDefault()
    if (!message.trim()) return
    localStorage.setItem('TrimP_last_feedback', JSON.stringify({ message: message.trim(), created_at: new Date().toISOString() }))
    setSent(true)
  }

  return <main className="feedback-page"><button className="back-link" onClick={() => onNavigate?.('sessions')}><ArrowLeft size={16} /> Back to conversations</button><section className="feedback-card"><span className="feedback-card-icon"><MessageSquare size={22} /></span><h1>Give feedback</h1><p>Tell us what made TrimPy useful, confusing, or worth improving.</p>{sent ? <div className="feedback-success"><CheckCircle2 size={18} /><span>Thanks. Your feedback was saved locally for this TrimPy workspace.</span></div> : <form onSubmit={submit}><textarea value={message} onChange={event => setMessage(event.target.value)} placeholder="Share your feedback…" rows="7" /><button className="feedback-submit" type="submit"><Send size={15} /> Send feedback</button></form>}</section></main>
}
