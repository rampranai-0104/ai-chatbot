import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import './index.css';

const API_URL = "https://ai-chatbot-ss8u.onrender.com";

function App() {
  const [sessionId] = useState(() => crypto.randomUUID());
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const messagesEndRef = useRef(null);

  const [activeTab, setActiveTab] = useState('chat');
  const [scrapeUrl, setScrapeUrl] = useState('');
  const [isScraping, setIsScraping] = useState(false);
  const [scrapeResult, setScrapeResult] = useState('');
  const [scrapeError, setScrapeError] = useState('');

  const [webSearchEnabled, setWebSearchEnabled] = useState(false);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    const userMessage = input.trim();
    setInput('');
    setIsStreaming(true);

    setMessages((prev) => [...prev, { role: 'user', text: userMessage }]);
    setMessages((prev) => [...prev, { role: 'assistant', text: '', status: '' }]);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          session_id: sessionId,
          message: userMessage,
          web_search: webSearchEnabled
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder('utf-8');
      
      let done = false;
      let buffer = '';

      while (!done) {
        const { value, done: readerDone } = await reader.read();
        done = readerDone;
        if (value) {
          buffer += decoder.decode(value, { stream: true });
          
          const lines = buffer.split('\n');
          buffer = lines.pop() || '';
          
          for (const line of lines) {
            const trimmed = line.trim();
            if (!trimmed) continue;
            
            let dataStr = trimmed;
            if (trimmed.startsWith('data:')) {
              dataStr = trimmed.slice(5).trim();
            }
            
            if (!dataStr) continue;

            try {
              const parsed = JSON.parse(dataStr);
              if (parsed.type === 'status') {
                setMessages((prev) => {
                  const newMsgs = [...prev];
                  const last = { ...newMsgs[newMsgs.length - 1] };
                  if (last.role === 'assistant') {
                    last.status = parsed.value;
                  }
                  newMsgs[newMsgs.length - 1] = last;
                  return newMsgs;
                });
              } else if (parsed.type === 'token') {
                setMessages((prev) => {
                  const newMsgs = [...prev];
                  const last = { ...newMsgs[newMsgs.length - 1] };
                  if (last.role === 'assistant') {
                    last.text += parsed.value;
                    last.status = '';
                  }
                  newMsgs[newMsgs.length - 1] = last;
                  return newMsgs;
                });
              } else if (parsed.type === 'sources') {
                setMessages((prev) => {
                  const newMsgs = [...prev];
                  const last = { ...newMsgs[newMsgs.length - 1] };
                  if (last.role === 'assistant') {
                    last.sources = parsed.value;
                  }
                  newMsgs[newMsgs.length - 1] = last;
                  return newMsgs;
                });
              } else if (parsed.type === 'done') {
                setMessages((prev) => {
                  const newMsgs = [...prev];
                  const last = { ...newMsgs[newMsgs.length - 1] };
                  if (last.role === 'assistant') {
                    last.status = '';
                  }
                  newMsgs[newMsgs.length - 1] = last;
                  return newMsgs;
                });
              }
            } catch (err) {
              console.error('Error parsing event data:', dataStr, err);
            }
          }
        }
      }
    } catch (error) {
      setMessages((prev) => {
        const newMsgs = [...prev];
        const last = { ...newMsgs[newMsgs.length - 1] };
        if (last.role === 'assistant') {
          last.text += (last.text ? '\n\n' : '') + `Error: ${error.message}`;
          last.status = '';
        }
        newMsgs[newMsgs.length - 1] = last;
        return newMsgs;
      });
    } finally {
      setIsStreaming(false);
    }
  };

  const handleScrape = async (e) => {
    e.preventDefault();
    if (!scrapeUrl.trim() || isScraping) return;
    
    setIsScraping(true);
    setScrapeResult('');
    setScrapeError('');
    
    try {
      const response = await fetch(`${API_URL}/scrape?url=${encodeURIComponent(scrapeUrl)}`);
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const data = await response.json();
      if (data.success) {
        setScrapeResult(data.content);
      } else {
        setScrapeError(data.error || 'Scraping failed');
      }
    } catch (err) {
      setScrapeError(err.message);
    } finally {
      setIsScraping(false);
    }
  };

  return (
    <div className="chat-container">
      <header className="chat-header">
        <h1>AI Chat Assistant</h1>
      </header>
      
      <div className="tabs-container">
        <button 
          className={`tab-button ${activeTab === 'chat' ? 'active' : ''}`}
          onClick={() => setActiveTab('chat')}
        >
          Chat
        </button>
        <button 
          className={`tab-button ${activeTab === 'scrape' ? 'active' : ''}`}
          onClick={() => setActiveTab('scrape')}
        >
          Web Scrape
        </button>
      </div>

      {activeTab === 'chat' ? (
        <>
          <main className="chat-messages">
        {messages.length === 0 && (
          <div className="empty-state">
            <p>Start a conversation by typing a message below.</p>
          </div>
        )}
        {messages.map((msg, idx) => (
          <div key={idx} className={`message-wrapper ${msg.role}`}>
            <div className={`message-bubble ${msg.role}`}>
              {msg.status && (
                <div className="status-indicator">
                  {msg.status === 'searching' ? 'Searching the web...' : msg.status}
                </div>
              )}
              {msg.text && (
                msg.role === 'assistant' ? (
                  <div className="markdown-content">
                    <ReactMarkdown 
                      remarkPlugins={[remarkGfm]} 
                      components={{
                        table: ({node, ...props}) => (
                          <div className="markdown-table-wrapper">
                            <table {...props} />
                          </div>
                        )
                      }}
                    >
                      {msg.text || ""}
                    </ReactMarkdown>
                  </div>
                ) : (
                  <div className="message-text">{msg.text}</div>
                )
              )}
              {msg.sources && msg.sources.length > 0 && (
                <div className="message-sources">
                  <strong>Sources:</strong>
                  <ul>
                    {msg.sources.map((src, i) => (
                      <li key={i}>
                        <a href={src.url} target="_blank" rel="noopener noreferrer">{src.title}</a>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {!msg.text && !msg.status && msg.role === 'assistant' && (
                <div className="typing-indicator">
                  <span></span><span></span><span></span>
                </div>
              )}
            </div>
          </div>
        ))}
        <div ref={messagesEndRef} />
      </main>
      
      <footer className="chat-input-area">
        <form onSubmit={handleSubmit}>
          <div className="web-search-toggle">
            <label>
              <input
                type="checkbox"
                checked={webSearchEnabled}
                onChange={(e) => setWebSearchEnabled(e.target.checked)}
                disabled={isStreaming}
              />
              Web Search: {webSearchEnabled ? 'ON' : 'OFF'}
            </label>
          </div>
          <div className="input-group">
            <input
              type="text"
              value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your message..."
            disabled={isStreaming}
          />
          <button type="submit" disabled={isStreaming || !input.trim()}>
            Send
          </button>
          </div>
        </form>
      </footer>
        </>
      ) : (
        <div className="scrape-panel">
          <form className="scrape-form" onSubmit={handleScrape}>
            <input
              type="url"
              value={scrapeUrl}
              onChange={(e) => setScrapeUrl(e.target.value)}
              placeholder="https://example.com"
              disabled={isScraping}
              required
            />
            <button type="submit" disabled={isScraping || !scrapeUrl.trim()}>
              {isScraping ? 'Scraping...' : 'Scrape'}
            </button>
          </form>
          
          {scrapeError && (
            <div className="scrape-error">
              Error: {scrapeError}
            </div>
          )}
          
          {scrapeResult && (
            <div className="scrape-result">
              {scrapeResult}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default App;
