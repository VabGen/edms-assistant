// src/components/MessageBubble.tsx

import React from 'react';

interface Props {
  role: 'user' | 'assistant';
  content: string;
}

const MessageBubble: React.FC<Props> = ({ role, content }) => {
  const isUser = role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-4`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-3 ${
          isUser
            ? 'bg-gradient-to-r from-blue-600 to-indigo-600 text-white'
            : 'bg-gray-700 text-gray-200'
        } shadow-md`}
      >
        <pre className="whitespace-pre-wrap break-words">
          {content}
        </pre>
      </div>
    </div>
  );
};

export default MessageBubble;