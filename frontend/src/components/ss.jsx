// src/components/AssistantWidget.jsx
import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';

const AssistantWidget = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false); // Для управления анимацией при нажатии
  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);

  // Приветствие при первом открытии
  useEffect(() => {
    if (isOpen && messages.length === 0) {
      setMessages([
        {
          role: 'assistant',
          content: 'Привет! Я — ваш помощник по СЭД. Чем могу помочь?',
          timestamp: new Date().toISOString(),
        },
      ]);
    }
  }, [isOpen, messages.length]);

  // Плавная прокрутка вниз
  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  const toggleWidget = () => {
    if (isAnimating) return;

    setIsAnimating(true);

    setTimeout(() => {
      setIsOpen(!isOpen);
      setIsAnimating(false);
    }, 400); // Длительность анимации масштабирования
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    const text = inputValue.trim();
    if (!text) return;

    const userMsg = {
      role: 'user',
      content: text,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInputValue('');
    setIsLoading(true);

    try {
      const res = await axios.post('http://localhost:8000/api/chat/ask', { question: text });
      const botMsg = {
        role: 'assistant',
        content: res.data.answer,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, botMsg]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Не удалось получить ответ. Попробуйте позже.',
          timestamp: new Date().toISOString(),
        },
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
        {
          role: 'assistant',
          content: 'Файл успешно загружен!',
          timestamp: new Date().toISOString(),
        },
      ]);
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Ошибка загрузки файла.',
          timestamp: new Date().toISOString(),
        },
      ]);
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {/* FAB-кнопка */}
      {!isOpen && (
        <div className="relative">
          <button
            onClick={toggleWidget}
            className={`w-14 h-14 rounded-full bg-blue-600 flex items-center justify-center shadow-lg transition-all duration-300 transform hover:scale-105 active:scale-95 ${
              isAnimating ? 'pointer-events-none opacity-70' : ''
            }`}
            style={{
              transitionTimingFunction: 'cubic-bezier(0.22, 1, 0.36, 1)',
            }}
            aria-label="Открыть помощника"
            disabled={isAnimating}
          >
            <span className="text-white font-bold text-lg">?</span>
          </button>

          {/* Анимация волн при наведении */}
          <div
            className={`absolute inset-0 rounded-full pointer-events-none ${isAnimating ? 'opacity-0' : ''}`}
            style={{
              background: 'radial-gradient(circle, transparent 40%, rgba(59, 130, 246, 0.2) 60%, transparent 80%)',
              animation: 'wavePulse 2s ease-in-out infinite',
              transform: 'scale(1)',
            }}
          />
        </div>
      )}

      {/* Основное окно чата */}
      {isOpen && (
        <div
          ref={chatContainerRef}
          className="bg-white rounded-xl shadow-xl overflow-hidden transition-all duration-400 ease-[cubic-bezier(0.22,1,0.36,1)] w-80 max-w-[320px] min-w-[300px]"
          style={{
            maxHeight: '80vh',
            opacity: 0,
            transform: 'scale(0.95)',
            animation: 'scaleIn 0.4s cubic-bezier(0.22, 1, 0.36, 1) forwards',
          }}
        >
          {/* Заголовок */}
          <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-gray-50">
            <h3 className="font-semibold text-gray-800 text-sm">AI Помощник СЭД</h3>
            <button
              onClick={() => setIsOpen(false)}
              className="text-gray-400 hover:text-gray-600 transition"
              aria-label="Закрыть"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Сообщения */}
          <div
            className="p-4 space-y-3 max-h-[calc(80vh-120px)] overflow-y-auto custom-scrollbar"
            style={{ scrollBehavior: 'smooth' }}
          >
            {messages.map((msg, idx) => (
              <div
                key={idx}
                className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
              >
                <div
                  className={`max-w-xs px-4 py-2 text-sm rounded-2xl ${
                    msg.role === 'user'
                      ? 'bg-blue-600 text-white rounded-br-none'
                      : 'bg-gray-100 text-gray-800 rounded-bl-none'
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))}
            {isLoading && (
              <div className="flex justify-start">
                <div className="bg-gray-100 px-4 py-2 rounded-2xl rounded-bl-none">
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

          {/* Инпут и кнопки */}
          <form onSubmit={handleSendMessage} className="p-4 border-t border-gray-200 flex items-center space-x-2">
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Сообщение..."
              className="flex-1 bg-gray-100 text-gray-800 text-sm rounded-full px-4 py-2 outline-none focus:ring-1 focus:ring-blue-500 transition"
              disabled={isLoading}
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center hover:bg-gray-300 transition transform hover:scale-105 active:scale-95"
              aria-label="Прикрепить файл"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586V16a2 2 0 01-2 2H4a2 2 0 01-2-2V4a2 2 0 012-2h8a2 2 0 012 2v2.828z" />
              </svg>
            </button>
            <button
              type="submit"
              disabled={!inputValue.trim() || isLoading}
              className="w-8 h-8 rounded-full bg-blue-600 flex items-center justify-center text-white disabled:bg-gray-300 transition transform hover:scale-105 active:scale-95"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
              </svg>
            </button>
          </form>
        </div>
      )}

      {/* Скрытый файловый инпут */}
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileUpload}
        className="hidden"
        accept=".doc,.docx,.xlsx,.pdf"
      />

      {/* Анимации */}
      <style jsx>{`
        @keyframes scaleIn {
          from {
            opacity: 0;
            transform: scale(0.95);
          }
          to {
            opacity: 1;
            transform: scale(1);
          }
        }

        @keyframes wavePulse {
          0% {
            transform: scale(1);
            opacity: 0.3;
          }
          50% {
            transform: scale(1.5);
            opacity: 0.1;
          }
          100% {
            transform: scale(1);
            opacity: 0.3;
          }
        }

        .custom-scrollbar {
          scrollbar-width: thin;
          scrollbar-color: #d1d5db #f9fafb;
        }

        .custom-scrollbar::-webkit-scrollbar {
          width: 6px;
        }

        .custom-scrollbar::-webkit-scrollbar-track {
          background: #f9fafb;
          border-radius: 3px;
        }

        .custom-scrollbar::-webkit-scrollbar-thumb {
          background: #d1d5db;
          border-radius: 3px;
        }

        .custom-scrollbar::-webkit-scrollbar-thumb:hover {
          background: #9ca3af;
        }
      `}</style>
    </div>
  );
};

export default AssistantWidget;