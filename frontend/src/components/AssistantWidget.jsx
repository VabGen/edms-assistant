import React, {useState, useRef, useEffect} from 'react';
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
    const fileInputRef = useRef(null);
    const messagesEndRef = useRef(null);
    const chatContainerRef = useRef(null);

    // Загрузка списка чатов
    const loadChats = async () => {
        try {
            const res = await axios.get('http://localhost:8000/api/chat/list', {
                withCredentials: true
            });
            setChats(res.data.chats);
            if (res.data.chats.length > 0 && !activeChatId) {
                setActiveChatId(res.data.chats[0].chat_id);
            }
        } catch (err) {
            console.error('Не удалось загрузить чаты:', err);
        }
    };

    // Загрузка истории чата
    const loadChatHistory = async (chatId) => {
        try {
            const res = await axios.get(`http://localhost:8000/api/chat/${chatId}/history`, {
                withCredentials: true
            });
            setMessages(res.data.messages);
        } catch (err) {
            console.error('Не удалось загрузить историю:', err);
            setMessages([]);
        }
    };

    // Создание нового чата
    const createNewChat = async () => {
        try {
            const res = await axios.post('http://localhost:8000/api/chat/new', {}, {
                withCredentials: true
            });
            setActiveChatId(res.data.chat_id);
            setMessages([]);
            loadChats();
        } catch (err) {
            console.error('Не удалось создать чат:', err);
        }
    };

    // Эффекты
    useEffect(() => {
        if (isOpen) {
            loadChats();
        }
    }, [isOpen]);

    useEffect(() => {
        if (activeChatId) {
            loadChatHistory(activeChatId);
        }
    }, [activeChatId]);

    // Приветствие для нового чата
    useEffect(() => {
        if (isOpen && messages.length === 0 && activeChatId) {
            setMessages([
                {
                    role: 'assistant',
                    content: 'Привет! Я — ваш помощник. Чем могу помочь?',
                    timestamp: new Date().toISOString(),
                },
            ]);
        }
    }, [isOpen, messages.length, activeChatId]);

    // Прокрутка
    useEffect(() => {
        if (messagesEndRef.current) {
            messagesEndRef.current.scrollIntoView({behavior: 'smooth'});
        }
    }, [messages]);

    // Закрытие по клику вне
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

        return () => {
            document.removeEventListener('mousedown', handleClickOutside);
        };
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
        }, 400);
    };

    const handleSendMessage = async (e) => {
        e.preventDefault();
        const text = inputValue.trim();
        if (!text || !activeChatId) return;

        const userMsg = {
            role: 'user',
            content: text,
            timestamp: new Date().toISOString(),
        };
        setMessages((prev) => [...prev, userMsg]);
        setInputValue('');
        setIsLoading(true);

        try {
            const res = await axios.post(
                `http://localhost:8000/api/chat/${activeChatId}/ask`,
                {question: text},
                {withCredentials: true}
            );
            const botMsg = {
                role: 'assistant',
                content: res.data.answer,
                timestamp: new Date().toISOString(),
            };
            setMessages((prev) => [...prev, botMsg]);
        } catch (err) {
            console.error('Ошибка при отправке сообщения:', err);
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
            await axios.post(
                'http://localhost:8000/api/files/upload',
                formData,
                {
                    headers: {'Content-Type': 'multipart/form-data'},
                    withCredentials: true,
                }
            );
            setMessages((prev) => [
                ...prev,
                {
                    role: 'assistant',
                    content: 'Файл успешно загружен!',
                    timestamp: new Date().toISOString(),
                },
            ]);
        } catch (err) {
            console.error('Ошибка загрузки файла:', err);
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
                <div className="relative flex items-center justify-center cursor-pointer">
                    <div
                        ref={(el) => {
                            if (el) {
                                el.onmouseenter = () => {
                                    el.style.opacity = '1';
                                    el.style.transform = 'translateX(-50%) scale(0.8)';
                                    el.style.animation = 'none';
                                    setTimeout(() => {
                                        el.style.animation = 'waveLeft 1.2s cubic-bezier(0.2, 0, 0.8, 1) forwards';
                                    }, 10);
                                };
                                el.onmouseleave = () => {
                                    el.style.opacity = '0';
                                    el.style.transform = 'translateX(-50%) scale(0.8)';
                                    el.style.animation = 'none';
                                };
                            }
                        }}
                        className="absolute inset-0 rounded-full opacity-0 transition-opacity duration-300"
                        style={{
                            boxShadow: '0 0 30px rgba(255, 215, 0, 0.6)',
                            transform: 'translateX(-50%) scale(0.8)',
                            left: '0',
                            right: 'auto',
                        }}
                    />
                    <div
                        ref={(el) => {
                            if (el) {
                                el.onmouseenter = () => {
                                    el.style.opacity = '1';
                                    el.style.transform = 'translateX(50%) scale(0.8)';
                                    el.style.animation = 'none';
                                    setTimeout(() => {
                                        el.style.animation = 'waveRight 1.2s cubic-bezier(0.2, 0, 0.8, 1) forwards';
                                    }, 10);
                                };
                                el.onmouseleave = () => {
                                    el.style.opacity = '0';
                                    el.style.transform = 'translateX(50%) scale(0.8)';
                                    el.style.animation = 'none';
                                };
                            }
                        }}
                        className="absolute inset-0 rounded-full opacity-0 transition-opacity duration-300"
                        style={{
                            boxShadow: '0 0 30px rgba(255, 215, 0, 0.6)',
                            transform: 'translateX(50%) scale(0.8)',
                            right: '0',
                            left: 'auto',
                        }}
                    />
                    <button
                        onClick={toggleWidget}
                        className="w-16 h-16 rounded-full bg-gradient-to-br from-blue-600 to-purple-700 flex items-center justify-center shadow-lg hover:shadow-xl transition-all duration-300 transform hover:scale-105 active:scale-95 relative z-10"
                        style={{
                            background: 'linear-gradient(135deg, #3b82f6, #6d28d9)',
                            boxShadow: '0 4px 20px rgba(0, 0, 0, 0.2), 0 0 10px rgba(106, 81, 255, 0.5)',
                        }}
                        aria-label="Открыть помощника"
                    >
                        <div className="flex space-x-1 relative">
                            <div
                                className="w-2 bg-white rounded-sm"
                                style={{
                                    height: '12px',
                                    transform: 'translate(-1px, -4px)',
                                    animation: 'eyeScan 8s ease-in-out infinite, blink 5s ease-in-out infinite',
                                }}
                            />
                            <div
                                className="w-2 bg-white rounded-sm"
                                style={{
                                    height: '12px',
                                    transform: 'translate(1px, -4px)',
                                    animation: 'eyeScan 8s ease-in-out infinite, blink 5s ease-in-out infinite',
                                }}
                            />
                        </div>
                        <div
                            className="absolute top-1 left-1 w-4 h-2 bg-white rounded-full opacity-30"
                            style={{transform: 'rotate(45deg)'}}
                        />
                    </button>
                </div>
            )}

            {/* Основное окно чата */}
            {(isOpen || isClosing) && (
                <div
                    ref={chatContainerRef}
                    className={`bg-white rounded-xl shadow-lg overflow-hidden w-80 max-w-[320px] min-w-[300px] ${
                        isClosing ? 'animate-fadeOutScale' : 'animate-fadeInScale'
                    }`}
                >
                    <div className="flex items-center justify-between p-4 border-b border-gray-200 bg-white">
                        <h3 className="font-semibold text-gray-800 text-sm">AI Помощник</h3>
                        <button
                            onClick={handleClose}
                            className="text-gray-400 hover:text-gray-600 transition"
                            aria-label="Закрыть"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none" viewBox="0 0 24 24"
                                 stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                      d="M6 18L18 6M6 6l12 12"/>
                            </svg>
                        </button>
                    </div>

                    {/* Панель управления чатами */}
                    <div className="px-4 py-2 border-b border-gray-200 flex justify-between items-center">
                        <button
                            onClick={() => setIsChatPanelOpen(!isChatPanelOpen)}
                            className="text-sm text-blue-600 hover:text-blue-800"
                        >
                            {isChatPanelOpen ? 'Скрыть чаты' : 'Мои чаты'}
                        </button>
                        <button
                            onClick={createNewChat}
                            className="text-sm bg-blue-100 text-blue-600 rounded-full px-2 py-1 hover:bg-blue-200"
                        >
                            + Новый
                        </button>
                    </div>

                    {isChatPanelOpen && (
                        <div className="p-2 max-h-32 overflow-y-auto border-b border-gray-100">
                            {chats.map((chat) => (
                                <div
                                    key={chat.chat_id}
                                    onClick={() => {
                                        setActiveChatId(chat.chat_id);
                                        setIsChatPanelOpen(false);
                                    }}
                                    className={`p-2 text-sm cursor-pointer rounded ${
                                        activeChatId === chat.chat_id ? 'bg-blue-100' : 'hover:bg-gray-100'
                                    }`}
                                >
                                    {chat.preview}
                                </div>
                            ))}
                            {chats.length === 0 && <div className="text-gray-400 text-sm p-2">Нет чатов</div>}
                        </div>
                    )}

                    <div className="p-4 space-y-3 max-h-[calc(80vh-180px)] overflow-y-auto custom-scrollbar">
                        {messages.map((msg, idx) => (
                            <div key={idx} className={`flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                <div
                                    className={`max-w-xs px-4 py-2 text-sm rounded-2xl break-words ${msg.role === 'user' ? 'bg-blue-600 text-white rounded-br-none' : 'bg-gray-100 text-gray-800 rounded-bl-none'}`}>
                                    {msg.content}
                                </div>
                            </div>
                        ))}
                        {isLoading && (
                            <div className="flex justify-start">
                                <div className="bg-gray-100 px-4 py-2 rounded-2xl rounded-bl-none">
                                    <div className="flex space-x-1">
                                        {[0, 1, 2].map((i) => (
                                            <div key={i} className="w-1.5 h-1.5 bg-gray-400 rounded-full animate-bounce"
                                                 style={{animationDelay: `${i * 0.1}s`}}/>
                                        ))}
                                    </div>
                                </div>
                            </div>
                        )}
                        <div ref={messagesEndRef}/>
                    </div>

                    <form onSubmit={handleSendMessage}
                          className="p-4 border-t border-gray-200 flex items-center space-x-2">
                        <input
                            type="text"
                            value={inputValue}
                            onChange={(e) => setInputValue(e.target.value)}
                            placeholder="Сообщение..."
                            className="flex-1 min-w-0 bg-gray-100 text-gray-800 text-sm rounded-full px-4 py-2 outline-none border border-gray-200 transition-all duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] focus:translate-y-[-2px] focus:scale-[1.02] focus:shadow-md focus:border-blue-400"
                            style={{overflow: 'hidden', whiteSpace: 'nowrap', textOverflow: 'ellipsis'}}
                            disabled={isLoading}
                        />
                        <button
                            type="button"
                            onClick={() => fileInputRef.current?.click()}
                            className="w-8 h-8 rounded-full bg-gray-200 flex items-center justify-center hover:bg-gray-300 transition transform hover:scale-105 active:scale-95"
                            aria-label="Прикрепить файл"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4 text-gray-600" fill="none"
                                 viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                      d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586V16a2 2 0 01-2 2H4a2 2 0 01-2-2V4a2 2 0 012-2h8a2 2 0 012 2v2.828z"/>
                            </svg>
                        </button>
                        <button
                            type="submit"
                            disabled={!inputValue.trim() || isLoading}
                            className="w-8 h-8 rounded-full bg-blue-400 flex items-center justify-center text-white disabled:bg-gray-300 transition transform hover:scale-105 active:scale-95"
                        >
                            <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none" viewBox="0 0 24 24"
                                 stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                      d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
                            </svg>
                        </button>
                    </form>
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