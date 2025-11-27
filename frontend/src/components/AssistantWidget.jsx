import React, {useState, useRef, useEffect, useCallback} from 'react';
import {assistantApi} from '../api/assistantApi';
import ParticleEffect from './ParticleEffect';
import ConfirmDialog from './ConfirmDialog';
import 'dayjs/locale/ru';
import dayjs from "dayjs";

dayjs.locale('ru');

// Анимация звуковых волн
const SoundWaveIndicator = () => (
    <div className="flex items-center justify-center space-x-0.5 w-5 h-5">
        {[0, 1, 2].map((i) => (
            <div
                key={i}
                className="w-0.5 bg-white rounded-full animate-sound-wave"
                style={{
                    height: `${Math.random() * 8 + 2}px`,
                    animationDelay: `${i * 0.1}s`,
                    animationDuration: `${0.6 + Math.random() * 0.2}s`,
                }}
            />
        ))}
    </div>
);

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
    const [confirmDialog, setConfirmDialog] = useState({isOpen: false, chatId: null});
    const [isListening, setIsListening] = useState(false);
    const [recognition, setRecognition] = useState(null);

    const fileInputRef = useRef(null);
    const messagesEndRef = useRef(null);
    const chatContainerRef = useRef(null);
    const fabRef = useRef(null);

    // === Инициализация Web Speech API ===
    useEffect(() => {
        if (typeof window !== 'undefined' && ('SpeechRecognition' in window || 'webkitSpeechRecognition' in window)) {
            const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
            const recognitionInstance = new SpeechRecognition();
            recognitionInstance.continuous = false;
            recognitionInstance.interimResults = false;
            recognitionInstance.lang = 'ru-RU';

            recognitionInstance.onresult = (event) => {
                const transcript = event.results[0][0].transcript;
                const correctedText = correctGrammar(transcript);
                setInputValue(correctedText);
            };

            recognitionInstance.onend = () => {
                setIsListening(false);
            };

            recognitionInstance.onerror = () => {
                setIsListening(false);
            };

            setRecognition(recognitionInstance);
        }
    }, []);

    const correctGrammar = (text) => {
        let corrected = text.trim();
        if (!corrected) return corrected;
        corrected = corrected.charAt(0).toUpperCase() + corrected.slice(1);
        corrected = corrected.replace(/([а-яё])([А-ЯЁ])/g, '$1 $2');
        if (!/[.!?]$/.test(corrected)) corrected += '.';
        const typoMap = {'зопрос': 'запрос', 'сдлеать': 'сделать', 'каксделать': 'как сделать'};
        Object.entries(typoMap).forEach(([wrong, right]) => {
            corrected = corrected.replace(new RegExp(wrong, 'gi'), right);
        });
        return corrected;
    };

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
            messagesEndRef.current.scrollIntoView({behavior: 'smooth'});
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
        if (isOpen) document.addEventListener('mousedown', handleClickOutside);
        return () => document.removeEventListener('mousedown', handleClickOutside);
    }, [isOpen, isClosing]);

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
        setConfirmDialog({isOpen: true, chatId});
    };

    const handleConfirmDelete = async () => {
        const {chatId} = confirmDialog;
        setConfirmDialog({isOpen: false, chatId: null});
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
        const userMsg = {role: 'user', content: inputValue, timestamp: new Date().toISOString()};
        setMessages(prev => [...prev, userMsg]);
        setInputValue('');
        setIsLoading(true);
        try {
            const res = await assistantApi.sendMessage(activeChatId, inputValue);
            const botMsg = {role: 'assistant', content: res.data.answer, timestamp: new Date().toISOString()};
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
        if (fabRef.current) {
            fabRef.current.style.animation = 'fabFadeOut 0.8s ease-out forwards';
        }
    };

    const handleClose = () => {
        setIsClosing(true);
        setTimeout(() => {
            setIsOpen(false);
            setIsClosing(false);
            setIsChatPanelOpen(false);
        }, 400);
    };

    const toggleListening = () => {
        if (!recognition) {
            alert('Распознавание речи не поддерживается в вашем браузере');
            return;
        }
        if (isListening) {
            recognition.stop();
        } else {
            recognition.start();
            setIsListening(true);
        }
    };

    return (
        <div className="fixed bottom-6 right-6 z-50">
            {!isOpen && (
                <div className="relative" ref={fabRef}>
                    <ParticleEffect
                        isActive={showParticles}
                        onComplete={() => {
                            setIsOpen(true);
                            setShowParticles(false);
                        }}
                    />
                    <button
                        onClick={handleFabClick}
                        className="w-20 h-20 rounded-full flex items-center justify-center relative overflow-hidden bg-white/10 backdrop-blur-xl border border-white/20 shadow-2xl shadow-blue-500/10 transition-all duration-300 group hover:shadow-blue-400/20 hover:scale-105"
                        aria-label="Открыть помощника"
                    >
                        {/* Фон — тёмно-синий градиент под стеклом */}
                        <div
                            className="absolute inset-0 rounded-full bg-gradient-to-br from-indigo-950/80 to-slate-900/80"/>

                        {/* Неоновые кольца — яркие и мерцающие */}
                        <div
                            className="absolute inset-2 rounded-full border-2 border-blue-400/50 animate-pulse-ring opacity-80"/>
                        <div
                            className="absolute inset-3 rounded-full border-2 border-cyan-300/60 animate-pulse-ring opacity-90"/>
                        <div className="absolute inset-4 rounded-full border-2 border-blue-300/70 animate-pulse-ring"/>

                        {/* Центральный текст */}
                        <span className="text-white text-lg font-medium tracking-wider animate-pulse z-10">AI</span>

                        {/* Внутреннее свечение при наведении */}
                        <div
                            className="absolute inset-0 rounded-full bg-gradient-to-br from-cyan-400/5 to-blue-500/10 opacity-0 group-hover:opacity-100 transition-opacity duration-300"/>

                        {/* Парящая тень */}
                        <div
                            className="absolute -bottom-1 left-1/2 transform -translate-x-1/2 w-16 h-2 bg-blue-500/20 rounded-full blur-md"></div>
                    </button>
                </div>
            )}

            {(isOpen || isClosing) && (
                <div
                    ref={chatContainerRef}
                    className={`bg-white/10 backdrop-blur-xl rounded-2xl shadow-2xl border border-white/20 overflow-hidden w-full max-w-[95vw] min-w-0 h-[600px] flex flex-col transition-all duration-300 ${
                        isClosing ? 'animate-fadeOutScale' : 'animate-fadeInScale'
                    }`}
                    style={{
                        width: isChatPanelOpen ? '624px' : '460px',
                        maxWidth: '95vw',
                        minWidth: '320px',
                    }}
                >
                    {/* Заголовок */}
                    <div
                        className="p-4 flex items-center justify-between border-b border-white/20 bg-white/5 backdrop-blur-sm rounded-t-2xl">
                        <div className="flex items-center gap-2">
                            <button
                                onClick={() => setIsChatPanelOpen(!isChatPanelOpen)}
                                className="p-1.5 rounded-md hover:bg-white/10 transition text-white"
                            >
                                {isChatPanelOpen ? (
                                    <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none"
                                         viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                              d="M6 18L18 6M6 6l12 12"/>
                                    </svg>
                                ) : (
                                    <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none"
                                         viewBox="0 0 24 24" stroke="currentColor">
                                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                              d="M4 6h16M4 12h16M4 18h16"/>
                                    </svg>
                                )}
                            </button>
                            <h3 className="font-semibold text-white">AI Помощник</h3>
                        </div>
                    </div>

                    <div className="flex-1 flex overflow-hidden">
                        {/* Панель чатов */}
                        {isChatPanelOpen && (
                            <div
                                className="w-3/5 min-w-0 bg-white/10 backdrop-blur-xl border-r border-white/20 flex flex-col">
                                <div className="p-3 mb-2 flex justify-between items-center border-b border-white/20">
                                    <h4 className="text-sm font-medium text-white">Мои чаты</h4>
                                </div>
                                <div className="p-2 flex-1 overflow-y-auto custom-scrollbar">
                                    {chats.map((chat) => (
                                        <div
                                            key={chat.chat_id}
                                            onClick={() => {
                                                setActiveChatId(chat.chat_id);
                                                setIsChatPanelOpen(false);
                                            }}
                                            className={`mb-2 p-2 text-sm cursor-pointer rounded-lg flex justify-between items-center ${
                                                activeChatId === chat.chat_id
                                                    ? 'bg-blue-500/30 border border-blue-400/50'
                                                    : 'hover:bg-white/10'
                                            } text-white transition-colors`}
                                        >
                                            <span className="truncate w-full">{chat.preview}</span>
                                            <button
                                                onClick={(e) => deleteChat(chat.chat_id, e)}
                                                className="p-1 rounded-full hover:bg-red-500/20 text-white/80"
                                            >
                                                <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none"
                                                     viewBox="0 0 24 24" stroke="currentColor">
                                                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
                                                </svg>
                                            </button>
                                        </div>
                                    ))}
                                    {chats.length === 0 && <div className="text-white/60 text-sm p-2">Нет чатов</div>}
                                </div>
                                <div className="p-5">
                                    <button
                                        onClick={createNewChat}
                                        className="w-29 py-2 gap-0 bg-blue-500/10 hover:bg-blue-300/10 rounded-full text-sm text-black transition flex items-center justify-center border border-indigo-400/50"
                                    >
                                        <span className="mr-1">
                                            <img src={'/fab-i.svg'} alt="Новый чат"
                                                 style={{width: '24px', height: '24px'}}/>
                                        </span>
                                        <span className="text-center">Новый чат</span>
                                    </button>
                                </div>
                            </div>
                        )}

                        {/* Основная область чата */}
                        <div className="flex-1 flex flex-col">
                            <div className="flex-1 p-4 overflow-y-auto custom-scrollbar">
                                {messages.map((msg, idx) => (
                                    <div key={idx}
                                         className={`mb-3 flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                                        <div
                                            className={`max-w-[85%] px-4 py-2.5 text-sm rounded-2xl break-words backdrop-blur-sm ${
                                                msg.role === 'user'
                                                    ? 'bg-blue-500/20 text-white border border-blue-400/30'
                                                    : 'bg-white/10 text-white/90 border border-white/20'
                                            } min-w-0`}
                                        >
                                            {msg.content}
                                        </div>
                                    </div>
                                ))}
                                {isLoading && (
                                    <div className="mb-3 flex justify-start">
                                        <div
                                            className="bg-white/10 px-4 py-2.5 rounded-2xl rounded-bl-none flex space-x-1 border border-white/20">
                                            {[0, 1, 2].map((i) => (
                                                <div
                                                    key={i}
                                                    className="w-1.5 h-1.5 bg-white/60 rounded-full animate-bounce"
                                                    style={{animationDelay: `${i * 0.1}s`}}
                                                />
                                            ))}
                                        </div>
                                    </div>
                                )}
                                <div ref={messagesEndRef}/>
                            </div>

                            {/* Форма ввода */}
                            <form onSubmit={handleSendMessage}
                                  className="p-4 border-t border-white/20 bg-white/5 backdrop-blur-sm">
                                <div className="flex items-center space-x-2">
                                    <button
                                        type="button"
                                        onClick={toggleListening}
                                        className={`w-10 h-10 rounded-full flex items-center justify-center transition ${
                                            isListening
                                                ? 'bg-red-500/90'
                                                : 'bg-white/10 border border-white/20 text-white/80 hover:bg-white/20'
                                        }`}
                                        aria-label={isListening ? 'Остановить запись' : 'Начать запись'}
                                    >
                                        {isListening ? <SoundWaveIndicator/> : (
                                            <svg xmlns="http://www.w3.org/2000/svg" className="w-5 h-5" fill="none"
                                                 viewBox="0 0 24 24" stroke="currentColor">
                                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                                      d="M19 11a7 7 0 01-7 7m0 0a7 7 0 01-7-7m7 7v4m0 0H8m4 0h4m-4-8a3 3 0 01-3-3V5a3 3 0 116 0v6a3 3 0 01-3 3z"/>
                                            </svg>
                                        )}
                                    </button>

                                    <input
                                        type="text"
                                        value={inputValue}
                                        onChange={(e) => setInputValue(e.target.value)}
                                        placeholder="Сообщение..."
                                        className="flex-1 bg-white/10 backdrop-blur-sm rounded-full px-4 py-2.5 text-white/90 outline-none border border-white/20 focus:ring-2 focus:ring-blue-400/50 focus:bg-white/20 transition placeholder:text-white/50 min-w-0"
                                        disabled={isLoading || isListening}
                                    />
                                    <label htmlFor="file-upload"
                                           className="cursor-pointer w-10 h-10 rounded-full bg-white/10 border border-white/20 flex items-center justify-center hover:bg-white/20 text-white/80">
                                        <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none"
                                             viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                                  d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586V16a2 2 0 01-2 2H4a2 2 0 01-2-2V4a2 2 0 012-2h8a2 2 0 012 2v2.828z"/>
                                        </svg>
                                    </label>
                                    <button
                                        type="submit"
                                        disabled={!inputValue.trim() || isLoading}
                                        className="w-10 h-10 rounded-full bg-blue-500/30 border border-blue-400/50 text-white flex items-center justify-center disabled:bg-gray-300/30 hover:bg-blue-400/40 transition"
                                    >
                                        <svg xmlns="http://www.w3.org/2000/svg" className="w-4 h-4" fill="none"
                                             viewBox="0 0 24 24" stroke="currentColor">
                                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2}
                                                  d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"/>
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

            <ConfirmDialog
                isOpen={confirmDialog.isOpen}
                title="Удаление чата"
                message="Вы уверены, что хотите удалить этот чат?"
                onConfirm={handleConfirmDelete}
                onCancel={() => setConfirmDialog({isOpen: false, chatId: null})}
            />
        </div>
    );
};

export default AssistantWidget;