import { useEffect, useRef } from 'react'
import Message from './Message'

export default function Thread({ messages }) {
  const bottomRef = useRef(null)
  const lastMsg   = messages[messages.length - 1]

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, lastMsg?.status])

  return (
    <div className="thread">
      <div className="thread-inner">
        {messages.map(msg => (
          <Message key={msg.id} msg={msg} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
