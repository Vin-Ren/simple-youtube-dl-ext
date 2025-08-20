const SERVER_URL = 'http://127.0.0.1:8765';
const videoStates = {}; 
const POLLING_ALARM_NAME = 'progress-poll-';

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    const videoId = message.tabId; 
    if (!videoId) return true;

    if (!videoStates[videoId]) {
        videoStates[videoId] = { status: 'loading', data: null, progress: 0, error: null, job_id: null };
    }

    switch (message.type) {
        case 'POPUP_INIT':
            if (videoStates[videoId].status === 'loading' || videoStates[videoId].status === 'error') {
                fetchVideoInfo(videoId, message.url);
            } else {
                broadcastState(videoId);
            }
            break;
        case 'START_DOWNLOAD':
            startDownload(videoId, message.url, message.formatId);
            break;
        case 'RESET_STATUS':
            videoStates[videoId].status = 'ready';
            videoStates[videoId].progress = 0;
            videoStates[videoId].job_id = null;
            videoStates[videoId].error = null;
            broadcastState(videoId);
            break;
    }
    return true;
});

async function fetchVideoInfo(videoId, url) {
    videoStates[videoId].status = 'loading'; broadcastState(videoId);
    try {
        const response = await fetch(`${SERVER_URL}/get_info?url=${encodeURIComponent(url)}`);
        if (!response.ok) throw new Error(`Backend error: ${response.status} ${await response.text()}`);
        videoStates[videoId].status = 'ready'; videoStates[videoId].data = await response.json();
    } catch (error) { videoStates[videoId].status = 'error'; videoStates[videoId].error = error.message; }
    broadcastState(videoId);
}

async function startDownload(videoId, url, formatId) {
    try {
        const response = await fetch(`${SERVER_URL}/download`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url, formatId }) });
        if (!response.ok) throw new Error(`Server error: ${response.status}`);
        const result = await response.json();
        videoStates[videoId].status = 'downloading'; videoStates[videoId].progress = 0; videoStates[videoId].job_id = result.job_id;
        chrome.alarms.create(POLLING_ALARM_NAME + videoId, { periodInMinutes: 0.03 });
    } catch (error) { videoStates[videoId].status = 'error'; videoStates[videoId].error = `Failed to start download: ${error.message}`; }
    broadcastState(videoId);
}

async function pollProgress(videoId) {
    const job_id = videoStates[videoId]?.job_id; if (!job_id) return;
    try {
        const response = await fetch(`${SERVER_URL}/progress/${job_id}`);
        if (!response.ok) { if (response.status === 404 && videoStates[videoId].status === 'downloading') { videoStates[videoId].status = 'completed'; videoStates[videoId].progress = 100; stopPolling(videoId); } return; }
        const update = await response.json();
        videoStates[videoId].status = update.status;
        videoStates[videoId].progress = update.progress;
        if (update.filepath) videoStates[videoId].filepath = update.filepath;
        if (update.status === 'error') videoStates[videoId].error = update.details;
        if (update.status === 'completed' || update.status === 'error') stopPolling(videoId);
        broadcastState(videoId);
    } catch (error) { videoStates[videoId].status = 'error'; videoStates[videoId].error = 'Lost connection to backend.'; stopPolling(videoId); broadcastState(videoId); }
}

function stopPolling(videoId) { chrome.alarms.clear(POLLING_ALARM_NAME + videoId); }
chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name.startsWith(POLLING_ALARM_NAME)) {
        const videoId = alarm.name.replace(POLLING_ALARM_NAME, '');
        if (videoStates[videoId]) pollProgress(videoId);
    }
});

function broadcastState(videoId) {
    chrome.runtime.sendMessage({ type: 'STATE_UPDATE', tabId: videoId, state: videoStates[videoId] });
}
