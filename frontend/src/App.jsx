// src/App.jsx
import React from 'react';
import AssistantWidget from './components/AssistantWidget';
import './index.css';

function App() {
    return (
        <div className="min-h-screen" style={
            {
                backgroundImage: "url('/b.jpg')",
                backgroundSize: "cover",
                backgroundRepeat: "no-repeat"
            }
        }>
            <AssistantWidget/>
        </div>
    );
}

export default App;