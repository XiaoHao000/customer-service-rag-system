/**
 * React 版前端组件（参考代码）。
 * 当前实际服务的是 static/index.html（原生 HTML），此文件仅作 React 迁移参考。
 * 使用时先编译：npx babel src/App.jsx --out-file ../app.js --presets=@babel/preset-react
 * 然后在 index.html 中引入编译后的 app.js。
 */
import React, { useState, useEffect, useRef } from 'react';

const App = () => {
  const [query, setQuery] = useState('');
  const [sourceFilter, setSourceFilter] = useState('');
  const [sessionId, setSessionId] = useState(null);
  const [answer, setAnswer] = useState('');
  const [history, setHistory] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const answerRef = useRef(null);

  const validSources = ['product_a', 'product_b'];

  useEffect(() => {
    fetch('/api/create_session', { method: 'POST' })
      .then(res => res.json())
      .then(data => setSessionId(data.session_id))
      .catch(err => console.error('初始化会话失败:', err));
  }, []);

  useEffect(() => {
    if (answerRef.current) {
      answerRef.current.scrollTop = answerRef.current.scrollHeight;
    }
  }, [answer]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    setIsLoading(true);
    setAnswer('');
    const requestBody = {
      query,
      source_filter: sourceFilter || null,
      session_id: sessionId
    };

    try {
      const response = await fetch('/api/query', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody)
      });
      const data = await response.json();

      if (data.is_streaming) {
        // RAG 流式响应，使用 WebSocket
        const wsUrl = `${location.protocol === 'https:' ? 'wss:' : 'ws:'}//${location.host}/api/stream`;
        const ws = new WebSocket(wsUrl);
        let accumulatedAnswer = '';

        ws.onopen = () => {
          ws.send(JSON.stringify(requestBody));
        };

        ws.onmessage = (event) => {
          const msg = JSON.parse(event.data);
          if (msg.type === 'token' && msg.token) {
            accumulatedAnswer += msg.token;
            setAnswer(accumulatedAnswer);
          } else if (msg.type === 'end') {
            ws.close();
          } else if (msg.type === 'error') {
            setAnswer('错误：' + msg.error);
            ws.close();
          }
        };

        ws.onerror = () => {
          setAnswer('错误：WebSocket 连接失败');
          setIsLoading(false);
        };

        ws.onclose = () => {
          setIsLoading(false);
          fetch(`/api/history/${sessionId}`)
            .then(res => res.json())
            .then(historyData => setHistory(historyData.history))
            .catch(err => console.error('获取历史失败:', err));
        };
      } else {
        setAnswer(data.answer);
        setIsLoading(false);
        const historyRes = await fetch(`/api/history/${sessionId}`);
        const historyData = await historyRes.json();
        setHistory(historyData.history);
      }
    } catch (err) {
      setAnswer('错误：无法获取答案');
      console.error('查询失败:', err);
      setIsLoading(false);
    }

    setQuery('');
    setSourceFilter('');
  };

  const handleClearHistory = async () => {
    try {
      await fetch(`/api/history/${sessionId}`, { method: 'DELETE' });
      setHistory([]);
      setAnswer('');
      alert('历史记录已清除');
    } catch (err) {
      console.error('清除历史失败:', err);
      alert('清除历史失败');
    }
  };

  return (
    <div className="max-w-3xl mx-auto">
      <h1 className="text-3xl font-bold text-center mb-6">集成问答系统</h1>
      <p className="text-center mb-4">会话ID: {sessionId || '加载中...'}</p>

      {/* 输入表单 */}
      <div className="bg-white p-6 rounded-lg shadow-md mb-6">
        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700">请输入您的问题</label>
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
              placeholder="输入问题..."
              disabled={isLoading}
            />
          </div>
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700">学科类别（可选）</label>
            <select
              value={sourceFilter}
              onChange={(e) => setSourceFilter(e.target.value)}
              className="mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500"
              disabled={isLoading}
            >
              <option value="">不限</option>
              {validSources.map((source) => (
                <option key={source} value={source}>{source}</option>
              ))}
            </select>
          </div>
          <button
            type="submit"
            className="w-full bg-indigo-600 text-white py-2 px-4 rounded-md hover:bg-indigo-700 disabled:bg-gray-400"
            disabled={isLoading}
          >
            {isLoading ? '处理中...' : '提交'}
          </button>
        </form>
      </div>

      {/* 答案显示 */}
      {answer && (
        <div className="bg-white p-6 rounded-lg shadow-md mb-6">
          <h2 className="text-xl font-semibold mb-2">答案</h2>
          <div
            ref={answerRef}
            className="max-h-96 overflow-y-auto prose prose-sm"
          >
            {answer.split('\n').map((line, i) => (
              <p key={i}>{line}</p>
            ))}
          </div>
        </div>
      )}

      {/* 历史记录 */}
      {history.length > 0 && (
        <div className="bg-white p-6 rounded-lg shadow-md">
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold">最近对话历史</h2>
            <button
              onClick={handleClearHistory}
              className="text-red-600 hover:text-red-800"
            >
              清除历史
            </button>
          </div>
          <div className="space-y-4">
            {history.map((entry, idx) => (
              <div key={idx}>
                <p className="font-medium">问: {entry.question}</p>
                <p className="text-gray-600">答: {entry.answer}</p>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

ReactDOM.createRoot(document.getElementById('root')).render(<App />);
