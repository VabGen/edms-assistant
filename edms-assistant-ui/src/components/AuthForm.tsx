// src/components/AuthForm.tsx

import React, { useState } from 'react';

interface Props {
  userId: string;
  token: string;
  onUserIdChange: (id: string) => void;
  onTokenChange: (token: string) => void;
}

const AuthForm: React.FC<Props> = ({
  userId,
  token,
  onUserIdChange,
  onTokenChange,
}) => {
  const [inputUserId, setInputUserId] = useState(userId);
  const [inputToken, setInputToken] = useState(token);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onUserIdChange(inputUserId);
    onTokenChange(inputToken);
    localStorage.setItem('edms_user_id', inputUserId);
    localStorage.setItem('edms_service_token', inputToken);
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <input
          type="text"
          value={inputUserId}
          onChange={(e) => setInputUserId(e.target.value)}
          placeholder="Ваш userId"
          className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all duration-300"
          required
        />
        <input
          type="password"
          value={inputToken}
          onChange={(e) => setInputToken(e.target.value)}
          placeholder="Ваш service_token"
          className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all duration-300"
          required
        />
      </div>
      <button
        type="submit"
        className="w-full px-4 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-medium rounded-xl transition-all duration-300"
      >
        Сохранить
      </button>
    </form>
  );
};

export default AuthForm;