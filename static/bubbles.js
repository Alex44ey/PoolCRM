// static/bubbles.js - Анимация пузырьков

document.addEventListener('DOMContentLoaded', function() {
    createBubbles();
});

function createBubbles() {
    const bubblesContainer = document.querySelector('.bubbles');
    if (!bubblesContainer) return;

    const bubbleCount = 50;

    for (let i = 0; i < bubbleCount; i++) {
        createBubble(bubblesContainer);
    }

    // Периодически создаём новые пузырьки
    setInterval(() => {
        createBubble(bubblesContainer);
    }, 2000);
}

function createBubble(container) {
    const bubble = document.createElement('div');
    bubble.className = 'bubble';

    // Случайные размеры (от 5px до 40px)
    const size = Math.random() * 35 + 5;
    bubble.style.width = size + 'px';
    bubble.style.height = size + 'px';

    // Случайная позиция по горизонтали
    bubble.style.left = Math.random() * 100 + '%';

    // Случайная длительность анимации (от 4 до 12 секунд)
    const duration = Math.random() * 8 + 4;
    bubble.style.animationDuration = duration + 's';

    // Случайная задержка
    bubble.style.animationDelay = Math.random() * 5 + 's';

    container.appendChild(bubble);

    // Удаляем пузырёк после окончания анимации
    setTimeout(() => {
        bubble.remove();
    }, duration * 1000);
}