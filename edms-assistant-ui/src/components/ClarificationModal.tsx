// src/components/ClarificationModal.tsx

import React from 'react';
import type { ChatResponse } from "../utils/api.ts";

interface Props {
  candidates: ChatResponse['candidates'];
  onSelect: (id: string) => void;  // ✅ Передаем ID сотрудника
  onCancel: () => void;
}

const ClarificationModal: React.FC<Props> = ({
  candidates,
  onSelect,
  onCancel,
}) => {
  const handleSelect = (candidateId: string) => {
    onSelect(candidateId);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-2xl p-6 w-full max-w-md shadow-2xl border border-gray-700">
        <h2 className="text-xl font-bold mb-4">Выберите сотрудника</h2>
        <ul className="space-y-2 mb-4 max-h-60 overflow-y-auto">
          {candidates?.map((c, index) => (
            <li key={c.id} className="border-b border-gray-700 pb-2 last:border-b-0">
              <button
                onClick={() => handleSelect(c.id)}  // ✅ Отправляем ID сотрудника
                className="w-full text-left px-4 py-2 hover:bg-gray-700 rounded-xl transition-colors duration-300"
              >
                {index + 1}. {c.first_name} {c.middle_name} {c.last_name}
              </button>
            </li>
          ))}
        </ul>
        <div className="flex justify-end gap-2">
          <button
            onClick={onCancel}
            className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-xl transition-colors duration-300"
          >
            Отмена
          </button>
        </div>
      </div>
    </div>
  );
};

export default ClarificationModal;