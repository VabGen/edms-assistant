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
  requires_hitl_decision?: boolean;  // Новое поле для HITL
  hitl_request?: any;  // Запрос HITL от LangGraph
  status?: string;
}

// ✅ Обновленная функция отправки сообщения
export const sendMessage = async (
  userId: string,
  serviceToken: string,  // Это токен EDMS
  message: string,
  documentId?: string,
  file?: File,
  threadId?: string
): Promise<ChatResponse> => {
  const formData = new FormData();
  formData.append('user_message', message);
  formData.append('user_id', userId);        // ✅ ID пользователя
  formData.append('edms_token', serviceToken); // ✅ Токен EDMS
  if (documentId) formData.append('document_id', documentId);
  if (file) formData.append('file', file);
  if (threadId) formData.append('thread_id', threadId);

  try {
    const response = await axios.post<ChatResponse>(
      `${API_BASE}/chat`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
          'Authorization': `Bearer ${serviceToken}`  // ✅ Токен в заголовке для валидации
        },
        timeout: 30000,
      }
    );

    const data = response.data;

    // ✅ Обрабатываем HITL прерывания от LangGraph
    if (data.requires_hitl_decision) {
      return {
        ...data,
        requires_clarification: true,
        clarification_type: "hitl_decision",
        candidates: [],
        candidates_list: data.hitl_request?.action_requests?.[0]?.description || "Требуется подтверждение действия",
        response: data.hitl_request?.action_requests?.[0]?.description || "Требуется подтверждение действия"
      };
    }

    return data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      throw new Error(`API Error: ${error.response?.data?.detail || error.message}`);
    } else if (error instanceof Error) {
      throw new Error(`Network Error: ${error.message}`);
    } else {
      throw new Error('Unknown error occurred');
    }
  }
};

// ✅ Новая функция для возобновления после HITL
export const resumeConversation = async (
  userId: string,
  serviceToken: string,
  decisions: any[],
  threadId: string
): Promise<ChatResponse> => {
  const formData = new FormData();
  formData.append('decisions', JSON.stringify(decisions));
  formData.append('thread_id', threadId);
  formData.append('user_id', userId);
  formData.append('edms_token', serviceToken);

  try {
    const response = await axios.post<ChatResponse>(
      `${API_BASE}/resume`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
          'Authorization': `Bearer ${serviceToken}`
        },
        timeout: 30000,
      }
    );

    return response.data;
  } catch (error) {
    if (axios.isAxiosError(error)) {
      throw new Error(`Resume Error: ${error.response?.data?.detail || error.message}`);
    } else if (error instanceof Error) {
      throw new Error(`Network Error: ${error.message}`);
    } else {
      throw new Error('Unknown error occurred');
    }
  }
};