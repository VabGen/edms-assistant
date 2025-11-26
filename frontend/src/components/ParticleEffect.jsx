// src/components/ParticleEffect.jsx
import { useEffect, useRef } from 'react';

export default function ParticleEffect({ isActive, onComplete }) {
  const containerRef = useRef(null);

  useEffect(() => {
    if (!isActive || !containerRef.current) return;

    const container = containerRef.current;
    // Очищаем предыдущие частицы
    container.innerHTML = '';

    for (let i = 0; i < 50; i++) {
      const dx = (Math.random() - 0.5) * 100;
      const dy = (Math.random() - 0.5) * 100;
      const delay = Math.random() * 0.3;
      const duration = 0.5 + Math.random() * 0.5;

      const particle = document.createElement('div');
      particle.className = 'absolute w-1 h-1 bg-blue-500 rounded-full pointer-events-none';
      particle.style.setProperty('--dx', `${dx}px`);
      particle.style.setProperty('--dy', `${dy}px`);
      particle.style.animation = `particleExplode ${duration}s ease-out ${delay}s forwards`;

      container.appendChild(particle);
    }

    // Запускаем callback по завершении всех анимаций
    const timer = setTimeout(onComplete, 1000);
    return () => clearTimeout(timer);
  }, [isActive, onComplete]);

  if (!isActive) return null;

  return (
    <div
      ref={containerRef}
      className="absolute inset-0 pointer-events-none z-10"
      aria-hidden="true"
    />
  );
}