document.addEventListener('DOMContentLoaded', async () => {
    const views = {
        status: document.getElementById('status-view'),
        success: document.getElementById('success-view'),
        main: document.getElementById('main-view'),
    };
    const spinner = document.getElementById('spinner');
    const statusText = document.getElementById('status-text');
    const thumbnailEl = document.getElementById('thumbnail');
    const videoTitleEl = document.getElementById('video-title');
    const videoDurationEl = document.getElementById('video-duration');
    const formatsList = document.getElementById('formats-list');
    const progressContainer = document.getElementById('progress-container');
    const progressBar = document.getElementById('progress-bar');
    const progressText = document.getElementById('progress-text');
    const downloadBtn = document.getElementById('download-btn');
    const filepathText = document.getElementById('filepath-text');
    const closeBtn = document.getElementById('close-btn');

    let currentVideoId = null, currentVideoUrl = '', selectedFormatId = null;
    let hasRenderedFormats = false;

    function getYouTubeVideoId(url) {
        const regex = /(?:https?:\/\/)?(?:www\.)?(?:youtube\.com\/(?:watch\?v=|embed\/|shorts\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})/;
        const match = url.match(regex);
        return match ? match[1] : null;
    }

    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    currentVideoUrl = tab.url;
    currentVideoId = getYouTubeVideoId(currentVideoUrl);

    if (!currentVideoId) {
        render({ status: 'error', error: 'Not a valid YouTube video page.' });
        return;
    }

    chrome.runtime.onMessage.addListener((message) => {
        if (message.type === 'STATE_UPDATE' && message.tabId === currentVideoId) {
            render(message.state);
        }
    });

    downloadBtn.addEventListener('click', () => {
        if (selectedFormatId) {
            chrome.runtime.sendMessage({
                type: 'START_DOWNLOAD', tabId: currentVideoId, url: currentVideoUrl,
                formatId: selectedFormatId
            });
        }
    });
    
    closeBtn.addEventListener('click', () => {
        chrome.runtime.sendMessage({ type: 'RESET_STATUS', tabId: currentVideoId });
    });
    
    chrome.runtime.sendMessage({ type: 'POPUP_INIT', tabId: currentVideoId, url: currentVideoUrl });

    function switchView(viewName) {
        Object.values(views).forEach(view => view.classList.add('hidden'));
        if (views[viewName]) views[viewName].classList.remove('hidden');
    }

    function render(state) {
        switch (state.status) {
            case 'loading':
                switchView('status');
                spinner.classList.remove('hidden');
                statusText.textContent = 'Fetching video data...';
                statusText.classList.remove('text-error');
                break;
            case 'ready':
                switchView('main');
                renderMainContent(state.data);
                downloadBtn.classList.remove('hidden');
                progressContainer.classList.add('hidden');
                downloadBtn.disabled = !selectedFormatId;
                break;
            case 'downloading':
                switchView('main');
                renderMainContent(state.data);
                downloadBtn.classList.add('hidden');
                progressContainer.classList.remove('hidden');
                renderProgress(state.progress, `Downloading... ${state.progress.toFixed(0)}%`);
                break;
            case 'postprocessing':
                switchView('main');
                renderMainContent(state.data);
                downloadBtn.classList.add('hidden');
                progressContainer.classList.remove('hidden');
                // THE FIX: Show the postprocessing progress starting from 0
                renderProgress(state.progress, `Postprocessing... ${state.progress.toFixed(0)}%`);
                break;
            case 'completed':
                switchView('success');
                filepathText.textContent = state.filepath || 'Your Downloads folder';
                break;
            case 'error':
                switchView('status');
                spinner.classList.add('hidden');
                statusText.textContent = state.error || 'An unknown error occurred.';
                statusText.classList.add('text-error');
                break;
        }
    }

    function renderMainContent(data) {
        if (!data) return;
        videoTitleEl.textContent = data.title;
        videoDurationEl.textContent = `Duration: ${data.duration}`;
        thumbnailEl.src = data.thumbnail;
        
        if (!hasRenderedFormats) {
            formatsList.innerHTML = '';
            formatsList.appendChild(createFormatOption({ id: 'mp3', label: 'MP3 (Audio Only)', size: '' }));
            data.formats.forEach(format => {
                formatsList.appendChild(createFormatOption(format));
            });
            hasRenderedFormats = true;
        }
    }

    function createFormatOption(format) {
        const option = document.createElement('button');
        option.className = 'btn btn-sm btn-ghost justify-between w-full font-normal format-option';
        option.dataset.formatId = format.id;
        option.innerHTML = `<span>${format.label}</span><span class="text-base-content/60">${format.size}</span>`;
        option.addEventListener('click', () => {
            document.querySelectorAll('.format-option').forEach(opt => {
                opt.classList.remove('btn-primary');
                opt.classList.add('btn-ghost');
            });
            option.classList.remove('btn-ghost');
            option.classList.add('btn-primary');
            selectedFormatId = option.dataset.formatId;
            downloadBtn.disabled = false;
        });
        return option;
    }

    function renderProgress(progress, text) {
        progressText.textContent = text;
        progressBar.value = progress;
    }
});
