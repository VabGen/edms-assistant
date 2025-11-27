'use client';

import { useEffect, useRef, useState } from 'react';

export default function AssistantEyes({ energyMode = 'high' }) {
  const eyeContainerRef = useRef(null);
  const [isBlinking, setIsBlinking] = useState(false);
  const [eyeOffset, setEyeOffset] = useState({ x: 0, y: 0 });
  const [cursorPos, setCursorPos] = useState({ x: 0, y: 0 });

  // Следим за курсором (если нужно)
  useEffect(() => {
    const handleMouseMove = (e) => {
      if (eyeContainerRef.current) {
        const rect = eyeContainerRef.current.getBoundingClientRect();
        const centerX = rect.left + rect.width / 2;
        const centerY = rect.top + rect.height / 2;
        const dx = (e.clientX - centerX) / 20; // Чем дальше — тем больше смещение
        const dy = (e.clientY - centerY) / 20;
        setCursorPos({ x: dx, y: dy });
      }
    };

    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  useEffect(() => {
    if (energyMode === 'low') return;

    // Моргание
    const blink = () => {
      setIsBlinking(true);
      setTimeout(() => setIsBlinking(false), 80);
    };

    // Синхронное движение глаз (слегка реагируют на курсор)
    const moveEyes = () => {
      const time = Date.now() * 0.002;
      const baseX = Math.sin(time) * 0.5;
      const baseY = Math.cos(time * 0.7) * 0.3;
      const x = baseX + cursorPos.x * 0.3;
      const y = baseY + cursorPos.y * 0.3;
      setEyeOffset({ x, y });
    };

    const blinkInterval = setInterval(blink, 3000 + Math.random() * 4000);
    const moveInterval = setInterval(moveEyes, 100);

    return () => {
      clearInterval(blinkInterval);
      clearInterval(moveInterval);
    };
  }, [energyMode, cursorPos]);

  return (
    <div
      ref={eyeContainerRef}
      className="relative flex space-x-1 z-10"
      style={{
        transform: `translate(${eyeOffset.x}px, ${eyeOffset.y}px)`,
        transition: 'transform 0.1s ease-out'
      }}
    >
      {/* Левый глаз */}
      <div className={`relative w-5 h-4 rounded-full bg-white/90 shadow-[0_0_12px_rgba(255,255,255,0.6)] transition-all duration-150 ${
        isBlinking ? 'scale-y-25' : ''
      }`}>
        <div className="absolute inset-0.5 rounded-full bg-gradient-to-br from-gray-600 to-gray-700 shadow-inner"></div>
        <div className="absolute top-0.5 left-0.5 w-1 h-1 bg-white rounded-full opacity-70 animate-pulse"></div>
        {/* Внутренняя тень для глубины */}
        <div className="absolute inset-0.5 rounded-full bg-black/10"></div>
        {/* Блик внутри глаза */}
        <div className="absolute top-0.5 right-0.5 w-0.5 h-0.5 bg-white rounded-full opacity-50"></div>
      </div>

      {/* Правый глаз */}
      <div className={`relative w-5 h-4 rounded-full bg-white/90 shadow-[0_0_12px_rgba(255,255,255,0.6)] transition-all duration-150 ${
        isBlinking ? 'scale-y-25' : ''
      }`}>
        <div className="absolute inset-0.5 rounded-full bg-gradient-to-br from-gray-600 to-gray-700 shadow-inner"></div>
        <div className="absolute top-0.5 left-0.5 w-1 h-1 bg-white rounded-full opacity-70 animate-pulse"></div>
        {/* Внутренняя тень */}
        <div className="absolute inset-0.5 rounded-full bg-black/10"></div>
        {/* Блик */}
        <div className="absolute top-0.5 right-0.5 w-0.5 h-0.5 bg-white rounded-full opacity-50"></div>
      </div>

      {/* Неоновое свечение вокруг глаз */}
      {energyMode !== 'low' && (
        <>
          <div className="absolute -inset-1 bg-gradient-to-br from-gray-400/10 to-gray-500/10 rounded-full blur-lg animate-pulse"></div>
          <div className="absolute -inset-2 bg-gradient-to-br from-gray-300/5 to-gray-400/5 rounded-full blur-xl animate-pulse"></div>
        </>
      )}
    </div>
  );
}