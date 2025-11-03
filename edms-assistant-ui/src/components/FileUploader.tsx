// src/components/FileUploader.tsx

import React, { useState } from 'react';

interface Props {
  file: File | null;
  onChange: (file: File | null) => void;
}

const FileUploader: React.FC<Props> = ({ file, onChange }) => {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const droppedFile = e.dataTransfer.files?.[0];
    if (droppedFile) {
      onChange(droppedFile);
    }
  };

  return (
    <div
      className={`border-2 border-dashed rounded-xl p-4 text-center cursor-pointer transition-colors ${
        isDragging ? 'border-blue-500 bg-blue-500 bg-opacity-10' : 'border-gray-600'
      }`}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      onClick={() => document.getElementById('file-upload')?.click()}
    >
      {file ? (
        <p className="text-sm text-gray-300 truncate">
          Выбран файл: {file.name}
        </p>
      ) : (
        <p className="text-sm text-gray-400">
          Перетащите файл сюда или нажмите, чтобы выбрать
        </p>
      )}
      <input
        id="file-upload"
        type="file"
        className="hidden"
        onChange={(e) => onChange(e.target.files?.[0] || null)}
      />
    </div>
  );
};

export default FileUploader;