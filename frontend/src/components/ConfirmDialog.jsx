// src/components/ConfirmDialog.jsx
import React from 'react';

export default function ConfirmDialog({ isOpen, title, message, onConfirm, onCancel }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Затемнение фона */}
      <div
        className="absolute inset-0 bg-black/30 backdrop-blur-sm"
        onClick={onCancel}
      />

      {/* Модальное окно */}
      <div className="relative bg-white/10 backdrop-blur-xl rounded-2xl shadow-2xl border border-white/20 max-w-md w-full p-6 text-white">
        <h3 className="text-2xl font-semibold mb-3">{title}</h3>
        <p className="text-white/80 mb-4">{message}</p>

        <div className="flex gap-3">
          <button
            onClick={onConfirm}
            className="flex-1 py-2 bg-red-500/90 hover:bg-red-400/90 rounded-lg transition text-white font-medium"
          >
            Удалить
          </button>
          <button
            onClick={onCancel}
            className="flex-1 py-2 bg-white/10 hover:bg-white/20 rounded-lg transition text-white font-medium"
          >
            Отмена
          </button>
        </div>
      </div>
    </div>
  );
}