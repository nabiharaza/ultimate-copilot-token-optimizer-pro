import { ArrowLeft, ArrowUpRight, Bug, CheckCircle2, Github, Heart, HelpCircle, Lightbulb, Linkedin, Mail, MessageSquare, Paperclip, PenLine, Send, ShieldCheck, Sparkles, Star, ThumbsUp, UserRound } from 'lucide-react'
import { useMemo, useState } from 'react'

const EMAIL = 'nabiha.raza30@gmail.com'
const GITHUB_URL = 'https://github.com/nabiharaza'
const LINKEDIN_URL = 'https://www.linkedin.com/in/nabiha-raza/'
const CATEGORIES = [
  ['Suggestion', Lightbulb],
  ['Issue / Bug', Bug],
  ['Praise', Heart],
  ['Question', HelpCircle],
]

export default function Feedback({ onNavigate }) {
  const [message, setMessage] = useState('')
  const [files, setFiles] = useState([])
  const [sent, setSent] = useState(false)
  const [category, setCategory] = useState('Suggestion')
  const remaining = Math.max(0, 1500 - message.length)
  const selectedFileNames = useMemo(() => files.map(file => file.name).join(' · '), [files])

  function submit(event) {
    event.preventDefault()
    if (!message.trim()) return
    localStorage.setItem('TrimP_last_feedback', JSON.stringify({ category, message: message.trim(), created_at: new Date().toISOString() }))
    const attachmentNote = files.length ? `\n\nPlease attach these files in your email: ${files.map(file => file.name).join(', ')}` : '\n\nScreenshots, logs, or short notes can be attached in your email composer.'
    const subject = encodeURIComponent(`TrimPy feedback: ${category}`)
    const body = encodeURIComponent(`[${category}]\n\n${message.trim()}${attachmentNote}`)
    window.location.href = `mailto:${EMAIL}?subject=${subject}&body=${body}`
    setSent(true)
  }

  return <main className="feedback-page">
    <button className="back-link" onClick={() => onNavigate?.('sessions')}><ArrowLeft size={16} /> Back to conversations</button>

    <section className="feedback-shell">
      <div className="feedback-main-card">
        <header className="feedback-hero">
          <span className="feedback-brand-mark"><span>T</span><i /><b /></span>
          <div><h1>Help make TrimPy better <Sparkles size={18} /></h1><p>Share your thoughts, report issues, or suggest ideas.</p></div>
        </header>

        <form onSubmit={submit}>
          <div className="feedback-category-tabs" role="tablist" aria-label="Feedback type">
            {CATEGORIES.map(([label, Icon]) => <button type="button" key={label} className={category === label ? 'active' : ''} onClick={() => setCategory(label)}><Icon size={15} /> {label}</button>)}
          </div>

          <label className="feedback-textbox">
            <textarea value={message} maxLength={1500} onChange={event => setMessage(event.target.value)} placeholder="Share your feedback..." rows="7" />
            <span>{remaining}/1500</span>
          </label>

          <label className="feedback-attachment">
            <Paperclip size={16} />
            <span><b>Attach screenshots, logs, or files</b><small>PNG, JPG, GIF, PDF, TXT up to 10MB</small></span>
            <input type="file" accept="image/*,.pdf,.txt,.log" multiple onChange={event => setFiles(Array.from(event.target.files || []))} />
          </label>
          {files.length > 0 && <small className="feedback-file-list">{selectedFileNames}</small>}

          <div className="feedback-followup">
            <label><input type="checkbox" checked readOnly /> <span>You can contact me by email for follow-up</span></label>
            <a href={`mailto:${EMAIL}`}><span>{EMAIL}</span><PenLine size={14} /></a>
          </div>

          {sent && <div className="feedback-success"><CheckCircle2 size={18} /><span>Your feedback was saved locally and your email composer was opened.</span></div>}

          <div className="feedback-submit-row">
            <button className="feedback-submit" type="submit" disabled={!message.trim()}><Send size={16} /> Send feedback</button>
            <span>We typically respond within 2-3 business days.</span>
          </div>
        </form>
      </div>

      <aside className="feedback-thanks-card">
        <div className="feedback-illustration" aria-hidden="true"><span><MessageSquare size={44} /></span><i><Heart size={17} /></i></div>
        <h2>Thank you!</h2>
        <p>Your feedback helps keep TrimPy lightweight and smart.</p>
        <ul>
          <li><CheckCircle2 size={15} /> All feedback is read by the product team</li>
          <li><CheckCircle2 size={15} /> We prioritize based on impact and frequency</li>
          <li><CheckCircle2 size={15} /> You help make TrimPy better for everyone</li>
        </ul>
        <div className="feedback-side-project"><Sparkles size={17} /><span><b>TrimPy is a side project</b><small>Built with care and late nights.</small></span></div>
      </aside>
    </section>

    <section className="feedback-connect-grid">
      <article>
        <span className="feedback-connect-icon"><UserRound size={20} /></span>
        <div><h3>Connect with me</h3><p>I would love to chat about ideas, feedback, or anything TrimPy.</p><div className="feedback-socials"><a href={LINKEDIN_URL} target="_blank" rel="noreferrer" aria-label="LinkedIn"><Linkedin size={22} /></a><a href={GITHUB_URL} target="_blank" rel="noreferrer" aria-label="GitHub"><Github size={22} /></a><a href={`mailto:${EMAIL}`} aria-label="Email"><Mail size={22} /></a></div><b>Let's build better tools together.</b></div>
      </article>
      <article>
        <span className="feedback-connect-icon"><ThumbsUp size={20} /></span>
        <div><h3>Like TrimPy?</h3><p>If TrimPy helps you save tokens and money, show some love.</p><div className="feedback-action-row"><a href={GITHUB_URL} target="_blank" rel="noreferrer"><Github size={16} /> Star on GitHub</a><a href={GITHUB_URL} target="_blank" rel="noreferrer"><ThumbsUp size={16} /> Like this repo</a></div><small>It motivates me a lot.</small></div>
      </article>
      <article>
        <span className="feedback-connect-icon"><Star size={20} /></span>
        <div><h3>Leave a review</h3><p>Share your experience and help others discover TrimPy.</p><div className="feedback-stars" aria-label="Five star rating">{Array.from({ length: 5 }, (_, index) => <Star key={index} size={23} fill="currentColor" />)}</div><a className="feedback-review-button" href={LINKEDIN_URL} target="_blank" rel="noreferrer">Write a review <ArrowUpRight size={14} /></a></div>
      </article>
    </section>

    <footer className="feedback-secure-note"><ShieldCheck size={14} /> Your feedback is secure and only used to improve TrimPy.</footer>
  </main>
}
