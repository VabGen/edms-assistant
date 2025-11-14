// src/utils/api.ts
import axios from 'axios';

// --- ИСПРАВЛЕНО: type-only import для ChatResponse ---
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
  message?: string; // Для clarification
  candidates_list?: string;
  thread_id?: string;
  requires_hitl_decision?: boolean;
  hitl_request?: any;
  status?: string;
}

// --- ДОБАВЛЕНО: Определение типа HITLDecision ---
export interface HITLDecision {
  type: 'approve' | 'edit' | 'reject';
  edited_action?: {
    name: string;
    args: Record<string, any>;
  };
  message?: string;
}

const API_BASE = 'http://127.0.0.1:8000';

export const sendMessage = async (
  userId: string,
  serviceToken: string, // Это токен EDMS
  message: string,
  documentId?: string,
  file?: File | undefined, // <-- Может быть undefined
  threadId?: string
): Promise<ChatResponse> => {
  const formData = new FormData();
  formData.append('user_message', message);
  formData.append('user_id', userId);
  // formData.append('edms_token', serviceToken); // <-- УБРАНО: токен в заголовке
  if (documentId) formData.append('document_id', documentId);
  if (file) formData.append('file', file); // <-- file может быть undefined, это нормально
  if (threadId) formData.append('thread_id', threadId);

  try {
    const response = await axios.post<ChatResponse>(
      `${API_BASE}/chat`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
          'Authorization': `Bearer ${serviceToken}` // ✅ Токен в заголовке
        },
        timeout: 30000,
      }
    );

    return response.data;
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

export const resumeConversation = async (
  userId: string,
  serviceToken: string,
  decisions: HITLDecision[], // <-- ТЕПЕРЬ ТОЧНО типизировано как HITLDecision[]
  threadId: string
): Promise<ChatResponse> => {
  const formData = new FormData();
  formData.append('decisions', JSON.stringify(decisions)); // <-- Преобразуем в строку
  formData.append('thread_id', threadId);
  formData.append('user_id', userId);
  // formData.append('edms_token', serviceToken); // <-- УБРАНО: токен в заголовке

  try {
    const response = await axios.post<ChatResponse>(
      `${API_BASE}/resume`,
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data',
          'Authorization': `Bearer ${serviceToken}` // ✅ Токен в заголовке
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