// src/utils/api.ts

import axios from 'axios';

const API_BASE = 'http://127.0.0.1:8000';

export interface ChatResponse {
  response: string;
  requires_clarification?: boolean;
  thread_id?: string;
  candidates?: Array<{
    id: string;
    last_name: string;
    first_name: string;
    middle_name: string;
    department: string;
    post: string;
  }>;
}

export const sendMessage = async (
  userId: string,
  serviceToken: string,
  message: string,
  documentId?: string,
  file?: File,
  threadId?: string,
  selectedCandidateId?: string
): Promise<ChatResponse> => {
  const formData = new FormData();
  formData.append('user_id', userId);
  formData.append('service_token', serviceToken);
  if (message) formData.append('message', message);
  if (documentId) formData.append('document_id', documentId);
  if (file) formData.append('file', file);
  if (threadId) formData.append('thread_id', threadId);
  if (selectedCandidateId) formData.append('selected_candidate_id', selectedCandidateId);

  const res = await axios.post<ChatResponse>(
    `${API_BASE}/chat`,
    formData,
    {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    }
  );

  return res.data;
};

// Для потоковой передачи
export const streamMessage = async (
  userId: string,
  serviceToken: string,
  message: string,
  documentId: string | undefined,
  file: File | undefined,
  threadId: string | undefined,
  onChunk: (chunk: string) => void,
  onComplete: () => void,
  onError: (err: string) => void
) => {
  const formData = new FormData();
  formData.append('user_id', userId);
  formData.append('service_token', serviceToken);
  if (message) formData.append('message', message);
  if (documentId) formData.append('document_id', documentId);
  if (file) formData.append('file', file);
  if (threadId) formData.append('thread_id', threadId);

  try {
    const response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    if (!response.body) {
      throw new Error('ReadableStream not supported');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const chunk = decoder.decode(value, { stream: true });
      onChunk(chunk);
    }

    onComplete();
  } catch (err) {
    onError(String(err));
  }
};