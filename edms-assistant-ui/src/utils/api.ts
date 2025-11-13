// src/utils/api.ts

import axios from 'axios';

const API_BASE = 'http://127.0.0.1:8000';

export interface ChatResponse {
  response?: string;
  requires_clarification?: boolean;
  clarification_type?: string;
  candidates?: Array<{
    id: string;
    last_name: string;
    first_name: string;
    middle_name: string;
    department?: string;
    post?: string;
  }>;
  candidates_list?: string;
  thread_id?: string;
  __interrupt__?: any;  // LangGraph прерывание
}

// ✅ Улучшенная функция отправки сообщения
export const sendMessage = async (
  userId: string,
  serviceToken: string,
  message: string,
  documentId?: string,
  file?: File,
  threadId?: string
): Promise<ChatResponse> => {
  const formData = new FormData();
  formData.append('user_id', userId);
  formData.append('service_token', serviceToken);
  formData.append('user_message', message);  // ✅ Правильное имя поля
  if (documentId) formData.append('document_id', documentId);
  if (file) formData.append('file', file);
  if (threadId) formData.append('thread_id', threadId);

  try {
    // ✅ Убираем `await` изнутри `axios.post` - он уже возвращает Promise
    const response = await axios.post<ChatResponse>(
      `${API_BASE}/chat`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        timeout: 30000,  // ✅ Добавляем таймаут
      }
    );

    const data = response.data;

    // ✅ Обрабатываем __interrupt__ от LangGraph
    if (data.__interrupt__) {
      return {
        ...data,
        requires_clarification: true,
        clarification_type: "employee_selection",
        candidates: data.__interrupt__.value.candidates,
        candidates_list: data.__interrupt__.value.message,
        response: data.__interrupt__.value.message
      };
    }

    return data;
  } catch (error) {
    // ✅ Лучшая обработка ошибок
    if (axios.isAxiosError(error)) {
      throw new Error(`API Error: ${error.response?.data?.detail || error.message}`);
    } else if (error instanceof Error) {
      throw new Error(`Network Error: ${error.message}`);
    } else {
      throw new Error('Unknown error occurred');
    }
  }
};