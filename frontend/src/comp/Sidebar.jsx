// Sidebar.jsx
import React from 'react';

export default function Sidebar({ user }) {
  if (!user) {
    return (
      <div className="w-64 bg-gray-800 p-6 flex flex-col">
        <div className="flex items-center mb-8">
          <div className="w-10 h-10 bg-gray-600 rounded-full flex items-center justify-center font-bold">
            ?
          </div>
          <div className="ml-3">
            <h3 className="font-bold">Гость</h3>
            <p className="text-sm text-gray-400">Не авторизован</p>
          </div>
        </div>
        <button className="mt-auto bg-red-600 hover:bg-red-700 text-white py-3 rounded-lg font-medium transition">
          Войти
        </button>
      </div>
    );
  }

  return (
    <div className="w-64 bg-gray-800 p-6 flex flex-col">
      <div className="flex items-center mb-8">
        <div className="w-10 h-10 bg-blue-600 rounded-full flex items-center justify-center font-bold">
          {user.username[0].toUpperCase()}
        </div>
        <div className="ml-3">
          <h3 className="font-bold">{user.username}</h3>
          <p className="text-sm text-gray-400">{user.role}</p>
        </div>
      </div>

      <button className="mt-auto bg-red-600 hover:bg-red-700 text-white py-3 rounded-lg font-medium transition">
        Выйти
      </button>
    </div>
  );
}