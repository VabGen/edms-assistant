import React from 'react';
import axios from 'axios';

export default function FileUploader() {
  const [file, setFile] = useState(null);
  const [message, setMessage] = useState('');

  const handleUpload = async () => {
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
      const res = await axios.post('http://localhost:8000/api/files/upload', formData, {
        headers: { 'Content-Type': 'multipart/form-data' }
      });
      setMessage(`✅ ${res.data.message}`);
      setFile(null);
    } catch (err) {
      setMessage('❌ Ошибка загрузки');
    }
  };

  return (
    <div className="p-4 bg-gray-800 rounded-lg mb-4">
      <h4 className="font-bold mb-2">Загрузить документ</h4>
      <input type="file" onChange={(e) => setFile(e.target.files[0])} className="mb-2" />
      <button onClick={handleUpload} className="bg-green-600 hover:bg-green-700 text-white px-4 py-2 rounded">
        Загрузить
      </button>
      {message && <p className="mt-2 text-sm">{message}</p>}
    </div>
  );
}