const themeToggle = document.getElementById('themeToggle');

function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
}

const saved = localStorage.getItem('theme') || 'dark';
applyTheme(saved);

if (themeToggle) {
    themeToggle.addEventListener('click', () => {
        const current = document.documentElement.getAttribute('data-theme');
        applyTheme(current === 'dark' ? 'light' : 'dark');
    });
}

const navBurger = document.getElementById('navBurger');
const navActions = document.getElementById('navActions');

if (navBurger && navActions) {
    navBurger.addEventListener('click', () => {
        navBurger.classList.toggle('active');
        navActions.classList.toggle('active');
    });
    navActions.querySelectorAll('a').forEach(link => {
        link.addEventListener('click', () => {
            navBurger.classList.remove('active');
            navActions.classList.remove('active');
        });
    });
}

document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.flash-message').forEach(msg => {
        setTimeout(() => {
            msg.style.animation = 'slideOut 0.3s ease forwards';
            setTimeout(() => msg.remove(), 300);
        }, 5000);

        const closeBtn = msg.querySelector('.flash-close');
        if (closeBtn) closeBtn.addEventListener('click', () => msg.remove());
    });
});
