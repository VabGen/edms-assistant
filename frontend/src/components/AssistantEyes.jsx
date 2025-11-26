// src/components/AssistantEyes.jsx
export default function AssistantEyes() {
    return (
        <div className="flex space-x-1 relative z-10">
            <div
                className="w-2 bg-gray-800 rounded-sm"
                style={{
                    height: '12px',
                    transform: 'translate(-1px, -4px)',
                    animation: 'eyeScan 8s cubic-bezier(0.3, 0, 0.7, 1) infinite, blink 5s ease-in-out infinite',
                }}
            />
            <div
                className="w-2 bg-gray-800 rounded-sm"
                style={{
                    height: '12px',
                    transform: 'translate(1px, -4px)',
                    animation: 'eyeScan 8s cubic-bezier(0.3, 0, 0.7, 1) infinite, blink 5s ease-in-out infinite',
                }}
            />
        </div>
    );
}