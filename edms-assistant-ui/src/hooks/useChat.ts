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
  // ✅ userId теперь берём из localStorage или из состояния
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

  // ✅ Функция для установки userId и сохранения в localStorage
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

      if (res.requires_clarification) {
        setRequiresClarification(true);
        setCandidates(res.candidates || []);
      } else {
        const botMsg: Message = {
          id: Date.now().toString(),
          role: 'assistant',
          content: res.response,
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

  const handleClarify = async (selectedId: string) => {
    if (!userId) {
      alert('Пожалуйста, введите ваш userId.');
      return;
    }
    if (!serviceToken) {
      alert('Пожалуйста, введите ваш service_token.');
      return;
    }

    setIsLoading(true);
    setRequiresClarification(false);

    try {
      const res = await sendMessage(
        userId,
        serviceToken,
        '',
        documentId || undefined,
        undefined,
        threadId!,
        selectedId
      );

      const botMsg: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        content: res.response,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, botMsg]);
      updateThreadId(res.thread_id || threadId);
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
    handleClarify,
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