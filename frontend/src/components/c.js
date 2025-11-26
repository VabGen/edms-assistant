import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';

const AssistantWidget = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [isClosing, setIsClosing] = useState(false);
  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [isChatPanelOpen, setIsChatPanelOpen] = useState(false);
  const [chatsLoaded, setChatsLoaded] = useState(false);

  const fileInputRef = useRef(null);
  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);
  const fabRef = useRef(null);

  // Загрузка чатов
  const loadChats = async () => {
    try {
      const res = await axios.get('http://localhost:8000/api/chat/list', { withCredentials: true });
      setChats(res.data.chats);
      setChatsLoaded(true);
      if (res.data.chats.length > 0 && !activeChatId) {
        setActiveChatId(res.data.chats[0].chat_id);
      }
    } catch (err) {
      console.error('Не удалось загрузить чаты:', err);
      setChatsLoaded(true);
    }
  };

  const loadChatHistory = async (chatId) => {
    try {
      const res = await axios.get(`http://localhost:8000/api/chat/${chatId}/history`, { withCredentials: true });
      setMessages(res.data.messages);
    } catch (err) {
      console.error('Не удалось загрузить историю:', err);
      setMessages([]);
    }
  };

  const createNewChat = async () => {
    try {
      const res = await axios.post('http://localhost:8000/api/chat/new', {}, { withCredentials: true });
      setActiveChatId(res.data.chat_id);
      setMessages([]);
      loadChats();
      setIsChatPanelOpen(false);
    } catch (err) {
      console.error('Не удалось создать чат:', err);
    }
  };

  // Удаление чата
  const deleteChat = async (chatId, e) => {
    e.stopPropagation();
    if (!window.confirm('Удалить чат?')) return;

    try {
      await axios.delete(`http://localhost:8000/api/chat/${chatId}`, { withCredentials: true });
      const updatedChats = chats.filter(chat => chat.chat_id !== chatId);
      setChats(updatedChats);

      if (activeChatId === chatId) {
        if (updatedChats.length > 0) {
          setActiveChatId(updatedChats[0].chat_id);
        } else {
          createNewChat();
        }
      }
    } catch (err) {
      console.error('Не удалось удалить чат:', err);
      alert('Ошибка при удалении чата');
    }
  };

  useEffect(() => {
    if (isOpen) {
      loadChats();
    }
  }, [isOpen]);

  useEffect(() => {
    if (isOpen && chatsLoaded && chats.length === 0 && !activeChatId) {
      createNewChat();
    }
  }, [isOpen, chatsLoaded, chats.length, activeChatId]);

  useEffect(() => {
    if (activeChatId) loadChatHistory(activeChatId);
  }, [activeChatId]);

  useEffect(() => {
    if (isOpen && messages.length === 0 && activeChatId) {
      setMessages([{
        role: 'assistant',
        content: 'Привет! Я — ваш помощник. Чем могу помочь?',
        timestamp: new Date().toISOString(),
      }]);
    }
  }, [isOpen, messages.length, activeChatId]);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (
        chatContainerRef.current &&
        !chatContainerRef.current.contains(e.target) &&
        isOpen &&
        !isClosing
      ) {
        handleClose();
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [isOpen, isClosing]);

  const toggleWidget = () => {
    if (isClosing) return;
    setIsOpen(!isOpen);
  };

  const handleClose = () => {
    setIsClosing(true);
    setTimeout(() => {
      setIsOpen(false);
      setIsClosing(false);
      setIsChatPanelOpen(false);
    }, 400);
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    const text = inputValue.trim();
    if (!text || !activeChatId) return;

    const userMsg = { role: 'user', content: text, timestamp: new Date().toISOString() };
    setMessages(prev => [...prev, userMsg]);
    setInputValue('');
    setIsLoading(true);

    try {
      const res = await axios.post(`http://localhost:8000/api/chat/${activeChatId}/ask`, { question: text }, { withCredentials: true });
      const botMsg = { role: 'assistant', content: res.data.answer, timestamp: new Date().toISOString() };
      setMessages(prev => [...prev, botMsg]);
    } catch (err) {
      console.error('Ошибка при отправке сообщения:', err);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Не удалось получить ответ. Попробуйте позже.',
        timestamp: new Date().toISOString(),
      }]);
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
        withCredentials: true,
      });
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Файл успешно загружен!',
        timestamp: new Date().toISOString(),
      }]);
    } catch (err) {
      console.error('Ошибка загрузки файла:', err);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Ошибка загрузки файла.',
        timestamp: new Date().toISOString(),
      }]);
    }
  };

  // Эффект распада FAB на частицы
  const handleFabClick = () => {
    const fab = fabRef.current;
    if (!fab) return;

    // Увеличиваем
    fab.style.transform = 'scale(1.2)';
    fab.style.transition = 'transform 0.2s ease-out';

    // Создаём частицы
    for (let i = 0; i < 50; i++) {
      const particle = document.createElement('div');
      particle.className = 'absolute w-1 h-1 bg-blue-500 rounded-full pointer-events-none';
      particle.style.left = `${Math.random() * 100}%`;
      particle.style.top = `${Math.random() * 100}%`;
      particle.style.animation = `particleExplode ${0.5 + Math.random() * 0.5}s ease-out forwards`;
      fab.appendChild(particle);
    }

    // Через 0.6s — открываем чат
    setTimeout(() => {
      toggleWidget();
      fab.style.opacity = '0';
      fab.style.transform = 'scale(0)';
      setTimeout(() => {
        fab.style.display = 'none';
        // Восстанавливаем видимость после открытия чата
        if (isOpen) {
          fab.style.display = 'block';
          fab.style.opacity = '1';
          fab.style.transform = 'scale(1)';
        }
      }, 400);
    }, 600);
  };

  return (
    <div className="fixed bottom-6 right-6 z-50">
      {/* FAB — с эффектом распада */}
      {!isOpen && (
        <div className="relative group" ref={fabRef}>
          <button
            onClick={handleFabClick}
            className="w-16 h-16 rounded-full flex items-center justify-center relative overflow-hidden transition-all duration-300"
            style={{
              background: 'linear-gradient(135deg, #f8fafc, #f1f5f9)',
              boxShadow: '0 4px 20px rgba(0, 0, 0, 0.08), 0 0 10px rgba(59, 130, 246, 0.1)',
            }}
            aria-label="Открыть помощника"
          >
            <div className="flex space-x-1 relative z-10">
              <div
                className="w-2 bg-gray-800 rounded-sm"
                style={{
                  height: '12px',
                  transform: 'translate(-1px, -4px)',
                  animation: 'eyeScan 8s cubic-bezier(0.3, 0, 0.7, 1) infinite, blink 5s ease-in-out infinite',
                }}
              />
              <div
                className="w-2 bg-gray-800 rounded-sm"
                style={{
                  height: '12px',
                  transform: 'translate(1px, -4px)',
                  animation: 'eyeScan 8s cubic-bezier(0.3, 0, 0.7, 1) infinite, blink 5s ease-in-out infinite',
                }}
              />
            </div>
            <div
              className="absolute top-1 left-1 w-4 h-2 bg-white rounded-full opacity-40 z-10"
              style={{ transform: 'rotate(45deg)' }}
            />
          </button>
          <div
            className="absolute inset-0 rounded-full pointer-events-none animate-inner-glow"
            style={{
              background: 'radial-gradient(circle, rgba(59,130,246,0.08) 0%, transparent 70%)',
              zIndex: -1,
            }}
          />
          <div
            className="absolute inset-0 rounded-full pointer-events-none animate-pulse-ring"
            style={{
              border: '2px solid transparent',
              background: 'conic-gradient(from 0deg, transparent, #3b82f6, #60a5fa, #3b82f6, transparent)',
              animation: 'pulseRing 4s ease-in-out infinite',
              filter: 'blur(2px)',
              zIndex: -2,
            }}
          />
          <div
            className="absolute inset-0 rounded-full pointer-events-none animate-outer-ring"
            style={{
              border: '1.5px solid transparent',
              background: 'conic-gradient(from 0deg, transparent, #60a5fa, #93c5fd, #60a5fa, transparent)',
              animation: 'outerRing 6s linear infinite',
              filter: 'blur(3px)',
              zIndex: -3,
            }}
          />
        </div>
      )}

      {/* Основное окно чата */}
      {(isOpen || isClosing) && (
        <div
          ref={chatContainerRef}
          className={`bg-white rounded-2xl shadow-xl overflow-hidden ${
            isChatPanelOpen ? 'w-[524px]' : 'w-[360px]'
          } max-w-[95vw] h-[600px] flex flex-col transition-all duration-300 ease-in-out ${
            isClosing ? 'animate-fadeOutScale' : 'animate-fadeInScale'
          }`}
        >
          {/* Header — с анимацией бургер → крестик */}
          <div className="p-4 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsChatPanelOpen(!isChatPanelOpen)}
                className="text-gray-500 hover:text-gray-700 p-1 rounded-md hover:bg-gray-100 transition"
                aria-label={isChatPanelOpen ? "Закрыть меню" : "Открыть меню"}
              >
                {isChatPanelOpen ? (
                  // Крестик
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                ) : (
                  // Бургер
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                )}
              </button>
              <h3 className="font-semibold text-gray-800">AI Помощник</h3>
            </div>
            <button
              onClick={handleClose}
              className="text-gray-400 hover:text-gray-600 p-1 rounded-md hover:bg-gray-100 transition"
              aria-label="Закрыть"
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          {/* Главный контент — с разрывом между панелью и чатом */}
          <div className="flex-1 flex overflow-hidden">
            {isChatPanelOpen && (
              <div className="w-[200px] bg-gray-800 text-white flex flex-col mr-1 rounded-tl-2xl rounded-bl-2xl">
                {/* Заголовок панели */}
                <div className="p-3 mb-2 flex justify-between items-center border-b border-gray-700">
                  <h4 className="text-sm font-medium">Мои чаты</h4>
                  <button
                    onClick={() => setIsChatPanelOpen(false)}
                    className="text-gray-400 hover:text-white p-1 rounded-full hover:bg-gray-700 transition"
                    aria-label="Закрыть меню"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>

                {/* Список чатов */}
                <div className="p-2 flex-1 overflow-y-auto">
                  {chats.map((chat) => (
                    <div
                      key={chat.chat_id}
                      onClick={() => {
                        setActiveChatId(chat.chat_id);
                        setIsChatPanelOpen(false);
                      }}
                      className={`mb-2 p-2 text-sm cursor-pointer rounded-lg flex justify-between items-center ${
                        activeChatId === chat.chat_id ? 'bg-blue-600' : 'hover:bg-gray-700'
                      }`}
                    >
                      <span className="truncate">{chat.preview}</span>
                      <button
                        onClick={(e) => deleteChat(chat.chat_id, e)}
                        className="text-gray-400 hover:text-red-400 p-1 rounded-full hover:bg-red-500/20"
                        aria-label="Удалить чат"
                      >
                        <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  ))}
                  {chats.length === 0 && <div className="text-gray-400 text-sm p-2">Нет чатов</div>}
                </div>

                {/* Кнопка "Новый чат" */}
                <div className="p-3 border-t border-gray-700">
                  <button
                    onClick={createNewChat}
                    className="w-full py-2 bg-blue-600 text-white text-sm rounded-full hover:bg-blue-500 transition"
                  >
                    + Новый чат
                  </button>
                </div>
              </div>
            )}

            {/* Основная область чата */}
            <div className="flex-1 flex flex-col overflow-hidden rounded-tr-2xl rounded-br-2xl">
              {/* Сообщения */}
              <div className="flex-1 p-4 overflow-y-auto custom-scrollbar">
                {messages.map((msg, idx) => (
                  <div key={idx} className={`mb-2 flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`max-w-[80%] px-4 py-2.5 text-sm rounded-2xl break-words ${
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
                  <div className="mb-2 flex justify-start">
                    <div className="bg-gray-100 px-4 py-2.5 rounded-2xl rounded-bl-none">
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

              {/* Input */}
              <form onSubmit={handleSendMessage} className="p-4">
                <div className="flex items-center space-x-2">
                  <input
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    placeholder="Сообщение..."
                    className="flex-1 bg-gray-100 text-gray-800 text-sm rounded-full px-4 py-2.5 outline-none border border-gray-200 transition-all duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] focus:translate-y-[-2px] focus:scale-[1.02] focus:shadow-md focus:border-blue-400"
                    disabled={isLoading}
                  />
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center hover:bg-gray-300 transition transform hover:scale-105 active:scale-95"
                    aria-label="Прикрепить файл"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586V16a2 2 0 01-2 2H4a2 2 0 01-2-2V4a2 2 0 012-2h8a2 2 0 012 2v2.828z"/>
                    </svg>
                  </button>
                  <button
                    type="submit"
                    disabled={!inputValue.trim() || isLoading}
                    className="w-10 h-10 rounded-full bg-blue-400 flex items-center justify-center text-white disabled:bg-gray-300 transition transform hover:scale-105 active:scale-95"
                  >
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
                    </svg>
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileUpload}
        className="hidden"
        accept=".doc,.docx,.xlsx,.pdf"
      />
    </div>
  );
};

export default AssistantWidget;
