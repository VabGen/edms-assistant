// src/hooks/useChat.ts
import {useState, useEffect} from "react";
import type {ChatResponse, HITLDecision} from "../utils/api.ts";
import {sendMessage, resumeConversation} from "../utils/api.ts";

export interface Message {
    id: string;
    role: 'user' | 'assistant';
    content: string;
    timestamp: Date;
}

export const useChat = () => {
    const [userId, setUserId] = useState<string>(() => localStorage.getItem('edms_user_id') || '');
    const [messages, setMessages] = useState<Message[]>([]);
    const [input, setInput] = useState('');
    const [file, setFile] = useState<File | null>(null);
    const [isLoading, setIsLoading] = useState(false);
    const [threadId, setThreadId] = useState<string | null>(null);

    useEffect(() => {
        const savedThreadId = localStorage.getItem('edms_current_thread_id');
        if (savedThreadId) {
            setThreadId(savedThreadId);
        } else {
            const newId = crypto.randomUUID();
            setThreadId(newId);
            localStorage.setItem('edms_current_thread_id', newId);
        }
    }, []);

    const [requiresClarification, setRequiresClarification] = useState(false);
    const [requiresHITL, setRequiresHITL] = useState(false); // <-- Используется для HITL решений (не уточнений)
    const [candidates, setCandidates] = useState<ChatResponse['candidates']>([]);
    const [serviceToken, setServiceToken] = useState<string>(() => localStorage.getItem('edms_service_token') || '');
    const [documentId, setDocumentId] = useState<string>('');

    const updateThreadId = (newId: string | null) => {
        setThreadId(newId);
        if (newId) {
            localStorage.setItem('edms_current_thread_id', newId);
        } else {
            localStorage.removeItem('edms_current_thread_id');
        }
    };

    const updateUserId = (newId: string) => {
        setUserId(newId);
        localStorage.setItem('edms_user_id', newId);
    };

    const handleSubmit = async () => {
        if (!userId || !serviceToken || (!input.trim() && !file)) return;

        if (!threadId) {
            console.error("No threadId available.");
            return;
        }

        const userMsg: Message = {id: Date.now().toString(), role: 'user', content: input, timestamp: new Date()};
        setMessages(prev => [...prev, userMsg]);
        setInput('');
        setIsLoading(true);

        try {
            const res = await sendMessage(userId, serviceToken, input, documentId, file || undefined, threadId); // <-- ИСПРАВЛЕНО: file -> file || undefined
            updateThreadId(res.thread_id || threadId);

            if (res.requires_clarification) {
                setRequiresClarification(true);
                setRequiresHITL(false); // Сбрасываем HITL, если было
                setCandidates(res.candidates || []);
                const clarificationMessage = res.message || res.response || 'Пожалуйста, уточните.';
                setMessages(prev => [...prev, {
                    id: Date.now().toString(),
                    role: 'assistant',
                    content: clarificationMessage,
                    timestamp: new Date()
                }]);
            } else if (res.requires_hitl_decision) {
                // Это настоящее HITL прерывание - требует решения через /resume
                setRequiresHITL(true);
                setRequiresClarification(false); // Сбрасываем clarification
                setMessages(prev => [...prev, {
                    id: Date.now().toString(),
                    role: 'assistant',
                    content: res.message || res.response || 'Требуется подтверждение действия.',
                    timestamp: new Date()
                }]);
            } else {
                setRequiresClarification(false);
                setRequiresHITL(false);
                setCandidates([]);
                setMessages(prev => [...prev, {
                    id: Date.now().toString(),
                    role: 'assistant',
                    content: res.response || 'Нет ответа.',
                    timestamp: new Date()
                }]);
            }
        } catch (err) {
            console.error(err);
            setMessages(prev => [...prev, {
                id: Date.now().toString(),
                role: 'assistant',
                content: `Ошибка: ${(err as Error).message}`,
                timestamp: new Date()
            }]);
        } finally {
            setIsLoading(false);
            setFile(null);
        }
    };

    // --- ИСПРАВЛЕНО: handleClarify теперь отправляет выбор как новое сообщение через handleSubmit ---
    const handleClarify = async (selection: string) => {
        setRequiresClarification(false);
        setCandidates([]);

        // Устанавливаем выбор как новое сообщение
        setInput(selection);
        // Вызов handleSubmit произойдет автоматически, так как input изменился
        // await handleSubmit(); // <-- Можно вызвать напрямую, если форма не отправляется автоматически
    };

    const handleHITLDecision = async (decisionType: 'approve' | 'edit' | 'reject', editContent?: string) => {
        setRequiresHITL(false);

        if (!threadId) {
            console.error('No thread ID for HITL resume');
            return;
        }

        // --- ЯВНО ОПРЕДЕЛЯЕМ ТИП decisions ---
        const decisions: HITLDecision[] = []; // <-- Явно типизируем как HITLDecision[]

        if (decisionType === 'approve') {
            decisions.push({type: 'approve'}); // <-- Добавляем элемент с правильным типом
        } else if (decisionType === 'reject') {
            decisions.push({type: 'reject', message: 'Действие отклонено пользователем'}); // <-- Правильный тип
        } else if (decisionType === 'edit' && editContent) {
            decisions.push({
                type: 'edit',
                edited_action: {
                    name: 'edited_action', // или конкретное имя инструмента
                    args: {content: editContent}
                }
            }); // <-- Правильный тип
        }

        // --- ПРОВЕРЯЕМ, ЧТО decisions не пустой (если логика требует решений) ---
        if (decisions.length === 0) {
            console.error("No decisions provided to resumeConversation");
            return;
        }

        try {
            setIsLoading(true);
            // --- ИСПРАВЛЕНО: Передаем типизированный массив decisions ---
            const res = await resumeConversation(userId, serviceToken, decisions, threadId);

            if (res.requires_hitl_decision) {
                setRequiresHITL(true);
                setRequiresClarification(false);
                setMessages(prev => [...prev, {
                    id: Date.now().toString(),
                    role: 'assistant',
                    content: res.message || res.response || 'Требуется дальнейшее подтверждение.',
                    timestamp: new Date()
                }]);
            } else if (res.requires_clarification) {
                setRequiresClarification(true);
                setRequiresHITL(false);
                setCandidates(res.candidates || []);
                const clarificationMessage = res.message || res.response || 'Пожалуйста, уточните выбор.';
                setMessages(prev => [...prev, {
                    id: Date.now().toString(),
                    role: 'assistant',
                    content: clarificationMessage,
                    timestamp: new Date()
                }]);
            } else {
                setMessages(prev => [...prev, {
                    id: Date.now().toString(),
                    role: 'assistant',
                    content: res.response || 'Обработка завершена.',
                    timestamp: new Date()
                }]);
            }
        } catch (err) {
            console.error(err);
            setMessages(prev => [...prev, {
                id: Date.now().toString(),
                role: 'assistant',
                content: `Ошибка: ${(err as Error).message}`,
                timestamp: new Date()
            }]);
        } finally {
            setIsLoading(false);
        }
    };

    const resetChat = () => {
        setMessages([]);
        setInput('');
        setFile(null);
        const newThreadId = crypto.randomUUID();
        updateThreadId(newThreadId);
        setDocumentId('');
        setRequiresClarification(false);
        setRequiresHITL(false);
        setCandidates([]);
    };

    return {
        messages,
        input,
        setInput,
        file,
        setFile,
        isLoading,
        handleSubmit,
        requiresClarification,
        requiresHITL,
        candidates,
        handleClarify,
        handleHITLDecision,
        resetChat,
        serviceToken,
        setServiceToken,
        documentId,
        setDocumentId,
        threadId,
        userId,
        updateUserId,
        setRequiresClarification,
        setRequiresHITL,
    };
};