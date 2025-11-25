// srccc/App.jsx
import React from 'react';
import AssistantWidget from './components/AssistantWidget';

function App() {
    return (
        <div className="min-h-screen bg-gray-50">
            <header className="p-6 bg-white shadow">
                <h1 className="text-2xl font-bold text-gray-800">Портал</h1>
            </header>
            <main className="p-6">
                <p className="text-gray-600">страница.</p>
            </main>
            <AssistantWidget/>
        </div>
    );
}

export default App;