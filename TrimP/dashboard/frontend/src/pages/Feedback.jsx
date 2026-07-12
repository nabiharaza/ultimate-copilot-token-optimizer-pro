import { ArrowLeft, CheckCircle2, Mail, MessageSquare, Paperclip, Send } from 'lucide-react'
import { useState } from 'react'

export default function Feedback({ onNavigate }) {
  const [message, setMessage] = useState('')
  const [files, setFiles] = useState([])
  const [sent, setSent] = useState(false)

  function submit(event) {
    event.preventDefault()
    if (!message.trim()) return
    localStorage.setItem('TrimP_last_feedback', JSON.stringify({ message: message.trim(), created_at: new Date().toISOString() }))
    const attachmentNote = files.length ? `\n\nPlease attach these files in your email: ${files.map(file => file.name).join(', ')}` : '\n\nScreenshots and photos can be attached in your email composer.'
    const subject = encodeURIComponent('TrimPy feedback')
    const body = encodeURIComponent(`${message.trim()}${attachmentNote}`)
    window.location.href = `mailto:nabiha.raza30@gmail.com?subject=${subject}&body=${body}`
    setSent(true)
  }

  return <main className="feedback-page"><button className="back-link" onClick={() => onNavigate?.('sessions')}><ArrowLeft size={16} /> Back to conversations</button><section className="feedback-card"><span className="feedback-card-icon"><MessageSquare size={22} /></span><h1>Give feedback</h1><p>Tell us what made TrimPy useful, confusing, or worth improving.</p>{sent ? <div className="feedback-success"><CheckCircle2 size={18} /><span>Your feedback was saved locally and your email composer was opened.</span></div> : <form onSubmit={submit}><textarea value={message} onChange={event => setMessage(event.target.value)} placeholder="Share your feedback…" rows="7" /><label className="feedback-attachment"><Paperclip size={15} /><span>Add screenshots or photos</span><input type="file" accept="image/*,.pdf,.txt,.log" multiple onChange={event => setFiles(Array.from(event.target.files || []))} /></label>{files.length > 0 && <small className="feedback-file-list">{files.map(file => file.name).join(' · ')}</small>}<p className="feedback-email-note"><Mail size={14} /> Opens an email to <b>nabiha.raza30@gmail.com</b>. Attach selected files in the email composer.</p><button className="feedback-submit" type="submit"><Send size={15} /> Email feedback</button></form>}</section></main>
}
