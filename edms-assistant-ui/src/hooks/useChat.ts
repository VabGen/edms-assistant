// src/hooks/useChat.ts

import { useState } from "react";
import { type ChatResponse, sendMessage, resumeConversation } from "../utils/api.ts";

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
  const [requiresHITL, setRequiresHITL] = useState(false);  // ✅ Локальное состояние для HITL
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

      // ✅ Проверяем, требуется ли HITL
      if (res.requires_hitl_decision) {
        setRequiresHITL(true);
        setRequiresClarification(false);
        setCandidates([]);

        // Добавляем сообщение о необходимости подтверждения
        const clarificationMsg: Message = {
          id: Date.now().toString(),
          role: 'assistant',
          content: res.response || 'Требуется подтверждение действия',
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, clarificationMsg]);
      }
      // ✅ Проверяем, требуется ли уточнение (например, выбор сотрудника)
      else if (res.requires_clarification) {
        setRequiresClarification(true);
        setRequiresHITL(false);
        setCandidates(res.candidates || []);

        // Добавляем сообщение с кандидатами в чат
        const clarificationMsg: Message = {
          id: Date.now().toString(),
          role: 'assistant',
          content: res.response || 'Пожалуйста, уточните выбор.',
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, clarificationMsg]);
      } else {
        setRequiresClarification(false);
        setRequiresHITL(false);
        setCandidates([]);

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
        content: `Ошибка: ${(err as Error).message}`,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
      setFile(null);
    }
  };

  // ✅ Обновленная функция обработки уточнений
  const handleClarify = async (selection: string) => {
    setRequiresClarification(false);
    setRequiresHITL(false);
    setCandidates([]);

    // Добавляем выбор пользователя в чат как сообщение
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
        selection,
        documentId || undefined,
        undefined,
        threadId || undefined
      );
      updateThreadId(res.thread_id || threadId);

      if (res.requires_hitl_decision) {
        setRequiresHITL(true);
        setRequiresClarification(false);
        const clarificationMsg: Message = {
          id: Date.now().toString(),
          role: 'assistant',
          content: res.response || 'Требуется подтверждение действия',
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, clarificationMsg]);
      } else if (res.requires_clarification) {
        setRequiresClarification(true);
        setRequiresHITL(false);
        setCandidates(res.candidates || []);
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
        content: `Ошибка: ${(err as Error).message}`,
        timestamp: new Date(),
      };
      setMessages(prev => [...prev, errorMsg]);
    } finally {
      setIsLoading(false);
    }
  };

  // ✅ Новая функция для обработки HITL решений
  const handleHITLDecision = async (decisionType: 'approve' | 'edit' | 'reject', editContent?: string) => {
    setRequiresHITL(false);

    if (!threadId) {
      console.error('No thread ID for HITL resume');
      return;
    }

    try {
      setIsLoading(true);

      let decisions: { type: string; edited_action?: { name: string; args: { content: string } }; message?: string; }[] = [];
      if (decisionType === 'approve') {
        decisions = [{ type: 'approve' }];
      } else if (decisionType === 'reject') {
        decisions = [{ type: 'reject', message: 'Действие отклонено пользователем' }];
      } else if (decisionType === 'edit' && editContent) {
        decisions = [{
          type: 'edit',
          edited_action: {
            name: 'edited_action',  // или конкретное имя инструмента
            args: { content: editContent }
          }
        }];
      }

      const res = await resumeConversation(userId, serviceToken, decisions, threadId);

      if (res.requires_hitl_decision) {
        setRequiresHITL(true);
        const clarificationMsg: Message = {
          id: Date.now().toString(),
          role: 'assistant',
          content: res.response || 'Требуется подтверждение действия',
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, clarificationMsg]);
      } else {
        const botMsg: Message = {
          id: Date.now().toString(),
          role: 'assistant',
          content: res.response || 'Обработка завершена.',
          timestamp: new Date(),
        };
        setMessages(prev => [...prev, botMsg]);
      }
    } catch (err) {
      console.error(err);
      const errorMsg: Message = {
        id: Date.now().toString(),
        role: 'assistant',
        content: `Ошибка: ${(err as Error).message}`,
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
    setRequiresHITL(false); // ✅ Сбрасываем HITL при сбросе чата
    setCandidates([]);
  };

  // ✅ Возвращаем setRequiresHITL в объекте
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
    setRequiresHITL, // ✅ Добавляем функцию обновления состояния HITL
  };
};