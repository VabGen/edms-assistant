// srccc/components/AssistantWidget.jsx
import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';

const AssistantWidget = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null); // Для ресайза
  const isResizingRef = useRef(false);

  // Приветствие при первом открытии
  useEffect(() => {
    if (isOpen && messages.length === 0) {
      setMessages([
        { role: 'assistant', content: 'Привет! Я — ваш помощник. Чем могу помочь?', timestamp: new Date().toISOString() },
      ]);
    }
  }, [isOpen, messages.length]);

  // Плавная прокрутка вниз при новых сообщениях
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // Ресайз окна
  const startResize = (e) => {
    e.preventDefault();
    isResizingRef.current = true;
    document.addEventListener('mousemove', handleResize);
    document.addEventListener('mouseup', stopResize);
  };

  const handleResize = (e) => {
    if (!isResizingRef.current || !chatContainerRef.current) return;

    const rect = chatContainerRef.current.getBoundingClientRect();
    const newWidth = Math.max(300, e.clientX - rect.left);
    const newHeight = Math.max(200, e.clientY - rect.top);

    chatContainerRef.current.style.width = `${newWidth}px`;
    chatContainerRef.current.style.height = `${newHeight}px`;
  };

  const stopResize = () => {
    isResizingRef.current = false;
    document.removeEventListener('mousemove', handleResize);
    document.removeEventListener('mouseup', stopResize);
  };

  const toggleWidget = () => setIsOpen(!isOpen);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    const text = inputValue.trim();
    if (!text) return;

    const userMsg = { role: 'user', content: text, timestamp: new Date().toISOString() };
    setMessages((prev) => [...prev, userMsg]);
    setInputValue('');
    setIsLoading(true);

    try {
      const res = await axios.post('http://localhost:8000/api/chat/ask', { question: text });
      const botMsg = { role: 'assistant', content: res.data.answer, timestamp: new Date().toISOString() };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Не удалось получить ответ. Попробуйте позже.', timestamp: new Date().toISOString() },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleFileUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      await axios.post('http://localhost:8000/api/files/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Файл успешно загружен!', timestamp: new Date().toISOString() },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { role: 'assistant', content: 'Ошибка загрузки файла.', timestamp: new Date().toISOString() },
      ]);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {/* FAB-кнопка */}
      {!isOpen && (
        <button
          onClick={toggleWidget}
          className="w-14 h-14 rounded-full bg-blue-600 flex items-center justify-center shadow-lg hover:bg-blue-700 transition-all duration-300 transform hover:scale-105 active:scale-95"
          style={{
            transitionTimingFunction: 'cubic-bezier(0.22, 1, 0.36, 1)',
          }}
          aria-label="Открыть помощника"
        >
          <span className="text-white font-bold text-lg">?</span>
        </button>
      )}

      {/* Основное окно чата */}
      {isOpen && (
        <div
          ref={chatContainerRef}
          className="bg-gray-900/80 backdrop-blur-xl rounded-xl shadow-2xl overflow-hidden transition-all duration-500 ease-[cubic-bezier(0.22, 1, 0.36, 1)]"
          style={{
            width: '320px',
            height: '400px',
            maxHeight: '80vh',
            minHeight: '200px',
            minWidth: '300px',
            transform: 'translateY(10px) scale(0.95)',
            opacity: 0,
            animation: 'fadeInUp 0.5s cubic-bezier(0.22, 1, 0.36, 1) forwards',
          }}
        >
          {/* Заголовок */}
          <div className="flex items-center justify-between p-4 border-b border-gray-800/50">
            <h3 className="font-semibold text-white text-sm">AI Помощник СЭД</h3>
            <button
              onClick={() => setIsOpen(false)}
              className="text-gray-400 hover:text-white transition"
              aria-label="Закрыть"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Сообщения */}
          <div
            className="p-4 space-y-3 max-h-[calc(100%-100px)] overflow-y-auto"
            style={{ scrollBehavior: 'smooth' }} // Плавный скролл
          >
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-xs px-3 py-2 text-sm rounded-2xl ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white rounded-br-none'
                      : 'bg-gray-800/70 text-gray-200 rounded-bl-none'
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-gray-800/70 px-3 py-2 rounded-2xl rounded-bl-none">
                  <div className="flex space-x-1">
                    {[0, 1, 2].map((i) => (
                      <div
                        key={i}
                        className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
                        style={{ animationDelay: `${i * 0.1}s` }}
                      />
                    ))}
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Инпут + кнопки */}
          <form onSubmit={handleSendMessage} className="p-4 border-t border-gray-800/50 flex items-center space-x-2">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Сообщение..."
              className="flex-1 bg-gray-800/70 text-white text-sm rounded-full px-4 py-2 outline-none focus:ring-1 focus:ring-blue-500 transition"
              disabled={isLoading}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="w-8 h-8 rounded-full bg-gray-800/50 flex items-center justify-center hover:bg-gray-700/50 transition transform hover:scale-105 active:scale-95"
              aria-label="Прикрепить файл"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586V16a2 2 0 01-2 2H4a2 2 0 01-2-2V4a2 2 0 012-2h8a2 2 0 012 2v2.828z" />
              </svg>
            </button>
            <button
              type="submit"
              disabled={!inputValue.trim() || isLoading}
              className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white disabled:bg-gray-700/50 transition transform hover:scale-105 active:scale-95"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </form>

          {/* Ручка для изменения размера */}
          <div
            className="absolute bottom-0 right-0 w-6 h-6 cursor-se-resize bg-transparent hover:bg-gray-700/30 rounded-bl-lg transition"
            onMouseDown={startResize}
            title="Изменить размер"
          >
            <svg xmlns="http://www.w3.org/2000/svg" className="w-3 h-3 text-gray-400 m-1" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 3h18v18H3z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v8m-4-4h8" />
            </svg>
          </div>
        </div>
      )}

      {/* Кнопка "X" для сворачивания */}
      {isOpen && (
        <button
          onClick={() => setIsOpen(false)}
          className="absolute bottom-[-16px] left-[-16px] w-10 h-10 rounded-full bg-blue-600 flex items-center justify-center shadow-lg hover:bg-blue-700 transition-all duration-300 transform hover:scale-105 active:scale-95"
          style={{
            transitionTimingFunction: 'cubic-bezier(0.22, 1, 0.36, 1)',
          }}
          aria-label="Свернуть помощника"
        >
          <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      )}

      {/* Скрытый файловый input */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileUpload}
        className="hidden"
        accept=".doc,.docx,.xlsx,.pdf"
      />

      {/* CSS-анимации */}
      <style jsx>{`
        @keyframes fadeInUp {
          from {
            opacity: 0;
            transform: translateY(10px) scale(0.95);
          }
          to {
            opacity: 1;
            transform: translateY(0) scale(1);
          }
        }
      `}</style>
    </div>
  );
};

export default AssistantWidget;
