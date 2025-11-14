// src/App.tsx
import {useChat} from './hooks/useChat';
import MessageBubble from './components/MessageBubble';
import ClarificationModal from './components/ClarificationModal';
import FileUploader from './components/FileUploader';
import AuthForm from './components/AuthForm';
import HITLModal from './components/HITLModal'; // <-- Убедитесь, что импортирован

function App() {
    // --- ИСПРАВЛЕНО: Добавлены setRequiresClarification и setRequiresHITL в деструктуризацию ---
    const {
        messages,
        input,
        setInput,
        file,
        setFile,
        isLoading,
        handleSubmit,
        requiresClarification,
        requiresHITL,
        candidates,
        handleClarify,
        handleHITLDecision,
        resetChat,
        serviceToken,
        setServiceToken,
        documentId,
        setDocumentId,
        threadId,
        userId,
        updateUserId,
        setRequiresClarification, // <-- ДОБАВЛЕНО
        setRequiresHITL,          // <-- ДОБАВЛЕНО
    } = useChat();

    return (
        <div
            className="min-h-screen bg-gradient-to-br from-gray-900 via-black to-gray-900 text-white flex items-center justify-center p-4">
            <div
                className="bg-gray-800 rounded-3xl shadow-2xl backdrop-blur-xl w-full max-w-4xl p-6 border border-gray-700">
                <header className="mb-6">
                    <h1 className="text-3xl font-bold mb-4 bg-clip-text text-transparent bg-gradient-to-r from-blue-400 to-purple-500">
                        EDMS Assistant
                    </h1>
                    <AuthForm
                        userId={userId}
                        token={serviceToken}
                        onUserIdChange={updateUserId}
                        onTokenChange={setServiceToken}
                    />
                    {threadId && (
                        <p className="text-sm text-gray-400 mt-2">
                            Thread ID: <span className="font-mono">{threadId}</span>
                        </p>
                    )}
                </header>

                <main className="flex-1 flex flex-col">
                    <div className="bg-gray-700 rounded-2xl p-4 mb-4 flex-1 overflow-y-auto max-h-[calc(100vh-250px)]">
                        {messages.length === 0 ? (
                            <p className="text-gray-500 text-center mt-10">
                                Начните диалог с агентом...
                            </p>
                        ) : (
                            messages.map((msg) => (
                                <MessageBubble
                                    key={msg.id}
                                    role={msg.role}
                                    content={msg.content}
                                />
                            ))
                        )}
                        {isLoading && (
                            <div className="flex justify-start mb-4">
                                <div className="bg-gray-600 text-gray-200 rounded-lg px-4 py-2">
                                    <span className="loading loading-dots loading-sm"></span> Агент печатает...
                                </div>
                            </div>
                        )}
                    </div>

                    <form
                        onSubmit={(e) => {
                            e.preventDefault();
                            handleSubmit();
                        }}
                        className="grid grid-cols-1 md:grid-cols-2 gap-4"
                    >
                        <div className="space-y-2">
                            <input
                                type="text"
                                value={documentId}
                                onChange={(e) => setDocumentId(e.target.value)}
                                placeholder="ID документа (опционально)"
                                className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all duration-300"
                            />
                            <FileUploader file={file} onChange={setFile}/>
                        </div>

                        <div className="space-y-2">
                            <input
                                type="text"
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                placeholder="Введите запрос..."
                                className="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-xl text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500 transition-all duration-300"
                                disabled={isLoading}
                            />
                            <div className="flex gap-2">
                                <button
                                    type="submit"
                                    className={`px-6 py-3 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 text-white font-medium rounded-xl transition-all duration-300 ${isLoading ? 'opacity-50 cursor-not-allowed' : ''}`}
                                    disabled={isLoading}
                                >
                                    Отправить
                                </button>
                                <button
                                    type="button"
                                    onClick={resetChat}
                                    className="px-6 py-3 bg-gray-600 hover:bg-gray-700 text-white font-medium rounded-xl transition-all duration-300"
                                >
                                    Сброс
                                </button>
                            </div>
                        </div>
                    </form>
                </main>
            </div>

            {/* ✅ Модальное окно уточнения */}
            {/* --- ИСПРАВЛЕНО: Добавлена проверка candidates --- */}
            {requiresClarification && candidates && candidates.length > 0 && (
                <ClarificationModal
                    candidates={candidates}
                    onSelect={handleClarify}
                    onCancel={() => setRequiresClarification(false)} // <-- ИСПРАВЛЕНО: используем функцию из хука
                />
            )}

            {/* ✅ Модальное окно HITL */}
            {requiresHITL && (
                <HITLModal
                    onApprove={() => handleHITLDecision('approve')}
                    onEdit={(content) => handleHITLDecision('edit', content)}
                    onReject={() => handleHITLDecision('reject')}
                    onCancel={() => setRequiresHITL(false)} // <-- ИСПРАВЛЕНО: используем функцию из хука
                />
            )}
        </div>
    );
}

export default App;