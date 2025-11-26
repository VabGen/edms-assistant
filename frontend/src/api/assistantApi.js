// src/api/assistantApi.js
import axios from 'axios';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export const assistantApi = {
    getChats: () => axios.get(`${API_BASE}/chat/list`, {withCredentials: true}),
    getHistory: (chatId) => axios.get(`${API_BASE}/chat/${chatId}/history`, {withCredentials: true}),
    createChat: () => axios.post(`${API_BASE}/chat/new`, {}, {withCredentials: true}),
    deleteChat: (chatId) => axios.delete(`${API_BASE}/chat/${chatId}`, {withCredentials: true}),
    sendMessage: (chatId, question) =>
        axios.post(`${API_BASE}/chat/${chatId}/ask`, {question}, {withCredentials: true}),
    uploadFile: (formData) =>
        axios.post(`${API_BASE}/files/upload`, formData, {
            headers: {'Content-Type': 'multipart/form-data'},
            withCredentials: true,
        }),
};