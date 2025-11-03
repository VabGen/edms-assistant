// src/components/ClarificationModal.tsx

import React from 'react';
import type {ChatResponse} from "../utils/api.ts";

interface Props {
  candidates: ChatResponse['candidates'];
  onSelect: (id: string) => void;
  onCancel: () => void;
}

const ClarificationModal: React.FC<Props> = ({
  candidates,
  onSelect,
  onCancel,
}) => {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-2xl p-6 w-full max-w-md shadow-2xl border border-gray-700">
        <h2 className="text-xl font-bold mb-4">Выберите кандидата</h2>
        <ul className="space-y-2 mb-4">
          {candidates?.map((c) => (
            <li key={c.id}>
              <button
                onClick={() => onSelect(c.id)}
                className="w-full text-left px-4 py-2 hover:bg-gray-700 rounded-xl transition-colors duration-300"
              >
                {c.last_name} {c.first_name} {c.middle_name}
              </button>
            </li>
          ))}
        </ul>
        <div className="flex gap-2">
          <button
            onClick={onCancel}
            className="px-4 py-2 bg-gray-600 hover:bg-gray-700 text-white rounded-xl transition-colors duration-300"
          >
            Отмена
          </button>
          <button
            onClick={onCancel}
            className="px-4 py-2 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white rounded-xl transition-colors duration-300"
          >
            Закрыть
          </button>
        </div>
      </div>
    </div>
  );
};

export default ClarificationModal;