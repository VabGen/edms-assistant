// src/components/AssistantWidget.jsx
import React, { useState, useRef, useEffect, useCallback } from 'react';
import { assistantApi } from '../api/assistantApi';
import AssistantEyes from './AssistantEyes';
import ParticleEffect from './ParticleEffect';

const AssistantWidget = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [isClosing, setIsClosing] = useState(false);
  const [showParticles, setShowParticles] = useState(false);
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

  // === Загрузка данных ===
  const loadChats = useCallback(async () => {
    try {
      const res = await assistantApi.getChats();
      setChats(res.data.chats);
      setChatsLoaded(true);
      if (res.data.chats.length > 0 && !activeChatId) {
        setActiveChatId(res.data.chats[0].chat_id);
      }
    } catch (err) {
      console.error('Failed to load chats:', err);
      setChatsLoaded(true);
    }
  }, [activeChatId]);

  const loadChatHistory = useCallback(async (chatId) => {
    try {
      const res = await assistantApi.getHistory(chatId);
      setMessages(res.data.messages);
    } catch (err) {
      console.error('Failed to load history:', err);
      setMessages([]);
    }
  }, []);

  // === Эффекты ===
  useEffect(() => {
    if (isOpen) loadChats();
  }, [isOpen, loadChats]);

  useEffect(() => {
    if (activeChatId) loadChatHistory(activeChatId);
  }, [activeChatId, loadChatHistory]);

  useEffect(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  // === Обработчики ===
  const createNewChat = async () => {
    try {
      const res = await assistantApi.createChat();
      setActiveChatId(res.data.chat_id);
      setMessages([]);
      await loadChats();
      setIsChatPanelOpen(false);
    } catch (err) {
      console.error('Failed to create chat:', err);
    }
  };

  const deleteChat = async (chatId, e) => {
    e.stopPropagation();
    if (!window.confirm('Удалить чат?')) return;
    try {
      await assistantApi.deleteChat(chatId);
      const updated = chats.filter(c => c.chat_id !== chatId);
      setChats(updated);
      if (activeChatId === chatId) {
        if (updated.length > 0) setActiveChatId(updated[0].chat_id);
        else await createNewChat();
      }
    } catch (err) {
      console.error('Failed to delete chat:', err);
      alert('Ошибка удаления');
    }
  };

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!inputValue.trim() || !activeChatId) return;

    const userMsg = { role: 'user', content: inputValue, timestamp: new Date().toISOString() };
    setMessages(prev => [...prev, userMsg]);
    setInputValue('');
    setIsLoading(true);

    try {
      const res = await assistantApi.sendMessage(activeChatId, inputValue);
      const botMsg = { role: 'assistant', content: res.data.answer, timestamp: new Date().toISOString() };
      setMessages(prev => [...prev, botMsg]);
    } catch (err) {
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
      await assistantApi.uploadFile(formData);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Файл успешно загружен!',
        timestamp: new Date().toISOString(),
      }]);
    } catch (err) {
      console.error('Upload error:', err);
      setMessages(prev => [...prev, {
        role: 'assistant',
        content: 'Ошибка загрузки файла.',
        timestamp: new Date().toISOString(),
      }]);
    }
  };

  const handleFabClick = () => {
    setShowParticles(true);
    setTimeout(() => {
      setIsOpen(true);
      setShowParticles(false);
    }, 600);
  };

  const handleClose = () => {
    setIsClosing(true);
    setTimeout(() => {
      setIsOpen(false);
      setIsClosing(false);
      setIsChatPanelOpen(false);
    }, 400);
  };

  // === Render ===
  return (
    <div className="fixed bottom-6 right-6 z-50">
      {!isOpen && (
        <div className="relative" ref={fabRef}>
          <ParticleEffect isActive={showParticles} onComplete={() => {}} />
          <button
            onClick={handleFabClick}
            className="w-16 h-16 rounded-full flex items-center justify-center relative overflow-hidden bg-gradient-to-br from-gray-50 to-gray-100 shadow-lg transition-all duration-300 hover:shadow-xl"
            aria-label="Открыть помощника"
          >
            <AssistantEyes />
            <div className="absolute top-1 left-1 w-2 h-2 bg-white rounded-full opacity-40 rotate-45" />
            <div className="absolute inset-0 rounded-full animate-inner-glow bg-gradient-radial from-blue-400/10 to-transparent" />
            <div className="absolute inset-0 rounded-full animate-pulse-ring border-2 border-transparent bg-gradient-conic from-transparent via-blue-400 to-transparent" />
            <div className="absolute inset-0 rounded-full animate-outer-ring border border-transparent bg-gradient-conic from-transparent via-blue-300 to-transparent" />
          </button>
        </div>
      )}

      {(isOpen || isClosing) && (
        <div
          ref={chatContainerRef}
          className={`bg-white rounded-2xl shadow-xl overflow-hidden w-full max-w-[95vw] h-[600px] flex flex-col transition-all duration-300 ${
            isClosing ? 'animate-fadeOutScale' : 'animate-fadeInScale'
          }`}
          style={{ width: isChatPanelOpen ? '524px' : '360px' }}
        >
          {/* Header */}
          <div className="p-4 flex items-center justify-between border-b border-gray-200">
            <div className="flex items-center gap-2">
              <button
                onClick={() => setIsChatPanelOpen(!isChatPanelOpen)}
                className="p-1.5 rounded-md hover:bg-gray-100 transition"
              >
                {isChatPanelOpen ? (
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                ) : (
                  <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                  </svg>
                )}
              </button>
              <h3 className="font-semibold text-gray-800">AI Помощник</h3>
            </div>
            <button onClick={handleClose} className="p-1.5 rounded-md hover:bg-gray-100">
              <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="flex-1 flex overflow-hidden">
            {isChatPanelOpen && (
              <div className="w-52 bg-gray-800 text-white flex flex-col">
                <div className="p-3 mb-2 flex justify-between items-center border-b border-gray-700">
                  <h4 className="text-sm font-medium">Мои чаты</h4>
                  <button onClick={() => setIsChatPanelOpen(false)} className="p-1 rounded-full hover:bg-gray-700">
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  </button>
                </div>
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
                      <button onClick={(e) => deleteChat(chat.chat_id, e)} className="p-1 rounded-full hover:bg-red-500/20">
                        <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    </div>
                  ))}
                  {chats.length === 0 && <div className="text-gray-400 text-sm p-2">Нет чатов</div>}
                </div>
                <div className="p-3 border-t border-gray-700">
                  <button onClick={createNewChat} className="w-full py-2 bg-blue-600 rounded-full text-sm hover:bg-blue-500 transition">
                    + Новый чат
                  </button>
                </div>
              </div>
            )}

            <div className="flex-1 flex flex-col">
              <div className="flex-1 p-4 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-300 scrollbar-track-transparent">
                {messages.map((msg, idx) => (
                  <div key={idx} className={`mb-3 flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                    <div
                      className={`max-w-[85%] px-4 py-2.5 text-sm rounded-2xl break-words ${
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
                  <div className="mb-3 flex justify-start">
                    <div className="bg-gray-100 px-4 py-2.5 rounded-2xl rounded-bl-none flex space-x-1">
                      {[0, 1, 2].map((i) => (
                        <div key={i} className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: `${i * 0.1}s` }} />
                      ))}
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </div>

              <form onSubmit={handleSendMessage} className="p-4 border-t border-gray-100">
                <div className="flex items-center space-x-2">
                  <input
                    type="text"
                    value={inputValue}
                    onChange={(e) => setInputValue(e.target.value)}
                    placeholder="Сообщение..."
                    className="flex-1 bg-gray-100 rounded-full px-4 py-2.5 text-gray-800 outline-none focus:ring-2 focus:ring-blue-400 focus:bg-white transition"
                    disabled={isLoading}
                  />
                  <label htmlFor="file-upload" className="cursor-pointer w-10 h-10 rounded-full bg-gray-200 flex items-center justify-center hover:bg-gray-300">
                    <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-gray-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586V16a2 2 0 01-2 2H4a2 2 0 01-2-2V4a2 2 0 012-2h8a2 2 0 012 2v2.828z"/>
                    </svg>
                  </label>
                  <button
                    type="submit"
                    disabled={!inputValue.trim() || isLoading}
                    className="w-10 h-10 rounded-full bg-blue-500 text-white flex items-center justify-center disabled:bg-gray-300 hover:bg-blue-400 transition"
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
        id="file-upload"
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