// src/components/HITLModal.tsx

import React, { useState } from 'react';

interface Props {
  onApprove: () => void;
  onEdit: (content: string) => void;
  onReject: () => void;
  onCancel: () => void;
}

const HITLModal: React.FC<Props> = ({
  onApprove,
  onEdit,
  onReject,
  onCancel,
}) => {
  const [editContent, setEditContent] = useState('');
  const [currentMode, setCurrentMode] = useState<'approve' | 'edit' | 'reject' | null>(null);

  const handleApprove = () => {
    onApprove();
    setCurrentMode(null);
  };

  const handleEdit = () => {
    if (editContent.trim()) {
      onEdit(editContent);
      setEditContent('');
      setCurrentMode(null);
    }
  };

  const handleReject = () => {
    onReject();
    setCurrentMode(null);
  };

  const handleCancel = () => {
    setCurrentMode(null);
    onCancel(); // ✅ Вызываем onCancel из пропсов
  };

  if (currentMode === 'edit') {
    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
        <div className="bg-gray-800 rounded-2xl p-6 w-full max-w-md shadow-2xl border border-gray-700">
          <h2 className="text-xl font-bold mb-4">Редактировать действие</h2>
          <textarea
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            placeholder="Введите изменения..."
            className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all duration-300 mb-4"
            rows={4}
          />
          <div className="flex justify-end gap-2">
            <button
              onClick={() => setCurrentMode(null)}
              className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-xl transition-colors duration-300"
            >
              Назад
            </button>
            <button
              onClick={handleEdit}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-xl transition-colors duration-300"
            >
              Сохранить
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-2xl p-6 w-full max-w-md shadow-2xl border border-gray-700">
        <h2 className="text-xl font-bold mb-4">Требуется подтверждение</h2>
        <p className="text-gray-300 mb-4">Выберите действие для подтверждения:</p>
        <div className="flex flex-col gap-2">
          <button
            onClick={handleApprove}
            className="px-4 py-3 bg-green-600 hover:bg-green-700 text-white rounded-xl transition-colors duration-300 text-left"
          >
            ✅ Подтвердить
          </button>
          <button
            onClick={() => setCurrentMode('edit')}
            className="px-4 py-3 bg-yellow-600 hover:bg-yellow-700 text-white rounded-xl transition-colors duration-300 text-left"
          >
            ✏️ Редактировать
          </button>
          <button
            onClick={handleReject}
            className="px-4 py-3 bg-red-600 hover:bg-red-700 text-white rounded-xl transition-colors duration-300 text-left"
          >
            ❌ Отклонить
          </button>
        </div>
        <div className="flex justify-end mt-4">
          <button
            onClick={handleCancel}
            className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-xl transition-colors duration-300"
          >
            Отмена
          </button>
        </div>
      </div>
    </div>
  );
};

export default HITLModal;