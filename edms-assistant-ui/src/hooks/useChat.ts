// src/hooks/useChat.ts

import { useState } from "react";
import { type ChatResponse, sendMessage } from "../utils/api.ts";

export interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

export const useChat = () => {
  const [userId, setUserId] = useState<string>(() => {
    return localStorage.getItem('edms_user_id') || '';
  });

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [threadId, setThreadId] = useState<string | null>(() => {
    return localStorage.getItem('edms_thread_id');
  });
  const [requiresClarification, setRequiresClarification] = useState(false);
  const [candidates, setCandidates] = useState<ChatResponse['candidates']>([]);
  const [serviceToken, setServiceToken] = useState<string>(() => {
    return localStorage.getItem('edms_service_token') || '';
  });
  const [documentId, setDocumentId] = useState<string>('');

  const updateThreadId = (newId: string | null) => {
    setThreadId(newId);
    if (newId) {
      localStorage.setItem('edms_thread_id', newId);
    } else {
      localStorage.removeItem('edms_thread_id');
    }
  };

  const updateUserId = (newId: string) => {
    setUserId(newId);
    localStorage.setItem('edms_user_id', newId);
  };

  const handleSubmit = async () => {
    if (!userId) {
      alert('Пожалуйста, введите ваш userId.');
      return;
    }
    if (!serviceToken) {
      alert('Пожалуйста, введите ваш service_token.');
      return;
    }
    if (!input.trim() && !file) return;

    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: input,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      const res = await sendMessage(
        userId,
        serviceToken,
        input,
        documentId || undefined,
        file || undefined,
        threadId || undefined
      );
      updateThreadId(res.thread_id || null);

      // ✅ Проверяем, есть ли уточнение (из __interrupt__ или обычного формата)
      if (res.requires_clarification) {
        setRequiresClarification(true);
        setCandidates(res.candidates || []);

        // ✅ Добавляем сообщение с кандидатами в чат
        const clarificationMsg: Message = {
          id: Date.now().toString(),
          role: 'assistant',
          content: res.response || 'Пожалуйста, уточните выбор.',
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, clarificationMsg]);
      } else {
        const botMsg: Message = {
          id: Date.now().toString(),
          role: 'assistant',
          content: res.response || 'Нет ответа.',
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, botMsg]);
      }
    } catch (err) {
      console.error(err);
      const errorMsg: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        content: 'Ошибка: не удалось отправить сообщение.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
      setFile(null);
    }
  };

  // ✅ Новая функция для обработки уточнений
  const handleClarify = async (selection: string) => {
    setRequiresClarification(false);
    setCandidates([]);

    // ✅ Добавляем выбор пользователя в чат как сообщение
    const userMsg: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: selection,
      timestamp: new Date(),
    };
    setMessages(prev => [...prev, userMsg]);

    try {
      setIsLoading(true);
      const res = await sendMessage(
        userId,
        serviceToken,
        selection, // ✅ Это может быть "2", ID или полное имя
        documentId || undefined,
        undefined,
        threadId || undefined
      );
      updateThreadId(res.thread_id || threadId);

      if (res.requires_clarification) {
        // ✅ Если снова нужна clarification, показываем снова
        setRequiresClarification(true);
        setCandidates(res.candidates || []);
        const clarificationMsg: Message = {
          id: Date.now().toString(),
          role: 'assistant',
          content: res.response || 'Пожалуйста, уточните выбор.',
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, clarificationMsg]);
      } else {
        // ✅ Обычный ответ
        const botMsg: Message = {
          id: Date.now().toString(),
          role: 'assistant',
          content: res.response || 'Нет ответа.',
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, botMsg]);
      }
    } catch (err) {
      console.error(err);
      const errorMsg: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        content: 'Ошибка: не удалось уточнить выбор.',
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  const resetChat = () => {
    setMessages([]);
    setInput('');
    setFile(null);
    updateThreadId(null);
    setDocumentId('');
    setRequiresClarification(false);
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
    candidates,
    handleClarify, // ✅ Теперь доступна
    resetChat,
    serviceToken,
    setServiceToken,
    documentId,
    setDocumentId,
    threadId,
    userId,
    updateUserId,
  };
};