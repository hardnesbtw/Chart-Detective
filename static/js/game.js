const loader = document.getElementById('gameLoader');
const content = document.getElementById('gameContent');
const tracksList = document.getElementById('tracksList');
const timerText = document.getElementById('timerValue');
const timerBox = document.getElementById('timer');
const form = document.getElementById('gameForm');
const submitBtn = document.getElementById('submitAnswer');
const selectedPanel = document.getElementById('selectedCountryPanel');
const selectedNameText = document.getElementById('selectedCountryName');
const selectedInput = document.getElementById('selectedCountryInput');
const countryBox = document.getElementById('countryGroups');
const searchInput = document.getElementById('countrySearchInput');
const searchInfo = document.getElementById('countrySearchMeta');
const emptySearch = document.getElementById('countryEmptyState');
const imageModal = document.getElementById('imageModal');
const modalImage = document.getElementById('modalImage');
const modalTitle = document.getElementById('modalTitle');
const loaderText = document.getElementById('loaderStatus');

const roundTime = Number(content.dataset.roundTime || 0);
const dataUrl = content.dataset.dataUrl;
const roundResultUrl = content.dataset.roundResultUrl;
const resultsUrl = content.dataset.resultsUrl;

// Слово "страна"
function pluralizeCountries(count) {
    const mod10 = count % 10;
    const mod100 = count % 100;
    if (mod10 === 1 && mod100 !== 11) return 'страна';
    if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return 'страны';
    return 'стран';
}

function markStep(step) {
    const el = document.querySelector(`[data-step="${step}"]`);
    if (!el) return;
    el.querySelector('i').className = 'ti ti-circle-check';
    el.classList.add('loader-step-done');
}

// Защита от возврата назад
history.pushState(null, '', window.location.href);
window.addEventListener('popstate', () => { window.location.href = '/'; });

// Очистка кэша при уходе со страницы
let leaving = false;
window.addEventListener('beforeunload', () => {
    if (!leaving) {
        navigator.sendBeacon('/api/game/abort');
    }
});


// Загрузка игры
async function loadGame() {
    loaderText.textContent = 'Загружаем чарт';

    const timeoutEl = document.getElementById('loaderTimeout');
    const countdownEl = document.getElementById('loaderAutoReloadText');
    let autoReloadTimer = null;
    let countdownInterval = null;

    // Через 2 минуты — показываем блок с кнопкой и запускаем обратный отсчёт
    const showTimeoutTimer = setTimeout(() => {
        if (timeoutEl) timeoutEl.hidden = false;

        let secondsLeft = 60;
        if (countdownEl) countdownEl.textContent = `Автоматическая перезагрузка через ${secondsLeft} сек.`;

        countdownInterval = setInterval(() => {
            secondsLeft -= 1;
            if (countdownEl) countdownEl.textContent = `Автоматическая перезагрузка через ${secondsLeft} сек.`;
        }, 1000);

        // Через 3 минуты (ещё 60 сек) — авто-перезагрузка
        autoReloadTimer = setTimeout(() => {
            clearInterval(countdownInterval);
            window.location.reload();
        }, 60_000);
    }, 120_000);

    const clearLoadTimers = () => {
        clearTimeout(showTimeoutTimer);
        clearTimeout(autoReloadTimer);
        clearInterval(countdownInterval);
    };

    const fetchPromise = fetch(dataUrl, { credentials: 'same-origin' });
    markStep('fetch');
    loaderText.textContent = 'Загружаем треки и аудио';

    let payload;
    try {
        const response = await fetchPromise;
        payload = await response.json();
    } catch {
        clearLoadTimers();
        alert('Не удалось загрузить данные раунда. Попробуйте ещё раз.');
        window.location.href = '/';
        return;
    }

    clearLoadTimers();

    if (!payload || payload.status !== 'ok') {
        const status = payload ? payload.status : '';
        if (status === 'skipped' || status === 'error') {
            leaving = true;
            window.location.href = roundResultUrl;
        } else if (status === 'finished') {
            leaving = true;
            window.location.href = resultsUrl;
        } else {
            window.location.href = '/';
        }
        return;
    }

    markStep('tracks');
    await new Promise(r => setTimeout(r, 250));
    markStep('audio');

    renderTracks(payload.tracks);
    content.hidden = false;
    loader.classList.add('is-done');
    setTimeout(() => { loader.hidden = true; }, 400);

    filterCountries(searchInput.value);
    startTimer();
}


// Отрисовка треков
function renderTracks(tracks) {
    tracksList.innerHTML = '';

    tracks.forEach((track, index) => {
        const card = document.createElement('div');
        card.className = 'track-card';

        const numberBox = document.createElement('div');
        numberBox.className = 'track-number';
        numberBox.textContent = index + 1;

        const imageBox = document.createElement('div');
        imageBox.className = 'track-image';
        if (track.image) {
            const img = new Image();
            img.src = track.image;
            img.loading = 'lazy';
            imageBox.appendChild(img);
            imageBox.addEventListener('click', () => {
                modalImage.src = track.image;
                modalTitle.textContent = track.title || '';
                imageModal.showModal();
            });
        } else {
            imageBox.innerHTML = '<div class="track-image-placeholder"><i class="ti ti-music"></i></div>';
        }

        const infoBox = document.createElement('div');
        infoBox.className = 'track-info';

        const titleBox = document.createElement('div');
        titleBox.className = 'track-title';
        titleBox.textContent = track.title || '';
        infoBox.appendChild(titleBox);

        const artistBox = document.createElement('div');
        artistBox.className = 'track-artist';
        artistBox.textContent = track.artist || '';
        infoBox.appendChild(artistBox);

        const playerBox = document.createElement('div');
        playerBox.className = 'track-player';
        if (track.mp3_url) {
            const audio = document.createElement('audio');
            audio.controls = true;
            audio.preload = 'auto';
            audio.src = track.mp3_url;
            audio.addEventListener('play', () => {
                tracksList.querySelectorAll('audio').forEach(a => { if (a !== audio) a.pause(); });
            });
            playerBox.appendChild(audio);
        } else if (track.spotify_url) {
            const a = document.createElement('a');
            a.href = track.spotify_url;
            a.target = '_blank';
            a.rel = 'noopener';
            a.className = 'btn btn-ghost btn-sm';
            a.innerHTML = '<i class="ti ti-brand-spotify-filled"></i><span>Spotify</span>';
            playerBox.appendChild(a);
        } else {
            playerBox.innerHTML = '<span class="track-no-audio"><i class="ti ti-music-off"></i> недоступно</span>';
        }

        card.append(numberBox, imageBox, infoBox, playerBox);
        tracksList.appendChild(card);
    });
}


const countryButtons = Array.from(countryBox.querySelectorAll('[data-country-option]'));
const countryGroups = Array.from(countryBox.querySelectorAll('[data-country-group]')).map(groupBox => ({
    box: groupBox,
    countText: groupBox.querySelector('[data-group-count]'),
    buttons: Array.from(groupBox.querySelectorAll('[data-country-option]')),
}));

const totalCountries = countryButtons.length;
const countryByIso = new Map(
    countryButtons.map(button => [(button.dataset.iso || '').toUpperCase(), {
        displayName: button.dataset.name || '',
        value: button.dataset.value || button.dataset.name || '',
    }])
);

let selectedName = '';
let selectedValue = '';

// Выбранная страна
function updateSelectedCountry() {
    selectedInput.value = selectedValue;
    selectedNameText.textContent = selectedName || 'Не выбрано';
    selectedPanel.classList.toggle('active', Boolean(selectedValue));
    submitBtn.disabled = !selectedValue;
}

// Поиск стран
function filterCountries(query = '') {
    const queryLower = query.trim().toLocaleLowerCase();
    let visibleCountries = 0;

    countryGroups.forEach(group => {
        let visibleInThisGroup = 0;
        group.buttons.forEach(button => {
            const matches = !queryLower || (button.dataset.search || '').includes(queryLower);
            button.hidden = !matches;
            if (matches) visibleInThisGroup++;
        });
        group.box.hidden = visibleInThisGroup === 0;
        if (group.countText) {
            group.countText.textContent = `${visibleInThisGroup} ${pluralizeCountries(visibleInThisGroup)}`;
        }
        if (queryLower && visibleInThisGroup > 0) {
            group.box.classList.add('open');
        } else {
            group.box.classList.remove('open');
        }
        visibleCountries += visibleInThisGroup;
    });

    emptySearch.hidden = visibleCountries > 0;
    countryBox.hidden = visibleCountries === 0;
    searchInfo.textContent = queryLower
        ? `Найдено ${visibleCountries} ${pluralizeCountries(visibleCountries)}`
        : `${totalCountries} ${pluralizeCountries(totalCountries)} доступно`;
}

// Выбор страны
function selectCountry(isoCode) {
    const iso = (isoCode || '').trim().toUpperCase();
    const country = countryByIso.get(iso);
    if (!country) return;

    selectedName = country.displayName;
    selectedValue = country.value;
    updateSelectedCountry();

    countryButtons.forEach(button => {
        const active = (button.dataset.iso || '').toUpperCase() === iso;
        button.classList.toggle('active', active);
        button.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
}

countryBox.addEventListener('click', e => {
    const toggle = e.target.closest('[data-group-toggle]');
    if (toggle) {
        toggle.closest('[data-country-group]').classList.toggle('open');
        return;
    }
    const button = e.target.closest('[data-country-option]');
    if (button) selectCountry(button.dataset.iso);
});

searchInput.addEventListener('input', () => filterCountries(searchInput.value));

updateSelectedCountry();
filterCountries('');


// Таймер
function startTimer() {
    let timeLeft = roundTime;
    timerText.textContent = timeLeft;

    const id = setInterval(() => {
        timeLeft--;
        timerText.textContent = timeLeft;
        if (timeLeft <= 10) timerBox.classList.add('timer-warning');
        if (timeLeft <= 0) {
            clearInterval(id);
            leaving = true;
            tracksList.querySelectorAll('audio').forEach(a => a.pause());
            form.submit();
        }
    }, 1000);

    form.addEventListener('submit', () => {
        leaving = true;
        clearInterval(id);
        submitBtn.disabled = true;
    }, { once: true });
}


// Закрытие обложки
imageModal.addEventListener('click', e => {
    if (e.target === imageModal) imageModal.close();
});

// Старт раунда
loadGame();
