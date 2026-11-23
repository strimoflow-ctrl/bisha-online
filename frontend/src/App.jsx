import React, { useState, useEffect, useRef } from 'react';
import { 
  Play, 
  Pause,
  Folder, 
  FileText, 
  Radio, 
  Award, 
  ChevronRight, 
  ArrowLeft, 
  Download, 
  Clock, 
  AlertCircle,
  Calendar,
  Sparkles,
  ExternalLink,
  Maximize2,
  Minimize2,
  RotateCcw,
  RotateCw,
  Gauge,
  Check,
  Settings
} from 'lucide-react';
import Hls from 'hls.js';
import { API_BASE_URL } from './config';

export default function App() {
  // Navigation state:
  // view: 'home' | 'batch' | 'player'
  const [view, setView] = useState('home');
  const [selectedBatch, setSelectedBatch] = useState(null);
  const [batchTab, setBatchTab] = useState('live'); // 'live' | 'content' | 'test'
  
  // Folder stack (for deep navigation & back)
  const [folderStack, setFolderStack] = useState([]); // [{ id, title }]
  const [folderItems, setFolderItems] = useState([]);
  
  // Overview state (Live / Upcoming / Recent)
  const [overviewData, setOverviewData] = useState({
    live_classes: [],
    upcoming_classes: [],
    recent_lectures: []
  });
  
  // Active playing video (Dedicated Player Page)
  const [activeVideo, setActiveVideo] = useState(null);

  // Data & loading states
  const [batches, setBatches] = useState([]);
  const [loadingBatches, setLoadingBatches] = useState(true);
  const [loadingFolder, setLoadingFolder] = useState(false);
  const [loadingOverview, setLoadingOverview] = useState(false);
  const [toastMessage, setToastMessage] = useState(null);

  // In-memory cache ref so we never refetch already-loaded data!
  const cacheRef = useRef({});
  const videoRef = useRef(null);
  const iframeRef = useRef(null);
  const hlsRef = useRef(null);
  const playerContainerRef = useRef(null);
  const [playbackSpeed, setPlaybackSpeed] = useState(1);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isPlaying, setIsPlaying] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [checkingPdf, setCheckingPdf] = useState(false);
  const [selectedQuality, setSelectedQuality] = useState('Auto');
  const [showQualityMenu, setShowQualityMenu] = useState(false);
  const [showSpeedMenu, setShowSpeedMenu] = useState(false);
  
  // Format seconds to mm:ss or hh:mm:ss
  const formatTime = (secs) => {
    if (!secs || isNaN(secs) || secs < 0) return '00:00';
    const totalSecs = Math.floor(secs);
    const m = Math.floor(totalSecs / 60);
    const s = totalSecs % 60;
    const h = Math.floor(m / 60);
    if (h > 0) {
      return `${h}:${String(m % 60).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
    }
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  };

  // High-Tech Cyber Decryption Shield State (With Dynamic Play Detection)
  const [shieldState, setShieldState] = useState({
    active: false,
    title: 'DISHA SECURE PROTOCOL',
    text: '📡 Connecting Disha Media Stream (Node #04)...',
    progress: 20
  });
  const shieldTimersRef = useRef([]);
  const waitingPlayRef = useRef(false);
  const currentShieldModeRef = useRef('start');

  const clearShieldTimers = () => {
    shieldTimersRef.current.forEach(t => clearTimeout(t));
    shieldTimersRef.current = [];
  };

  // Progressive countdown holds for a FULL 5 SECONDS once video frames physically start rendering (playerState === 1)
  const startDecryptionCountdown = (mode) => {
    clearShieldTimers();
    if (mode === 'start') {
      setShieldState({
        active: true,
        title: 'DISHA SECURE PROTOCOL',
        text: '🟢 Audio Stream Active • Decrypting Video Stream...',
        progress: 25
      });
      shieldTimersRef.current.push(
        setTimeout(() => {
          setShieldState(s => ({ ...s, text: '⚡ Node ASIA-SOUTH1 Decrypting Stream [1080P]...', progress: 55 }));
        }, 1200),
        setTimeout(() => {
          setShieldState(s => ({ ...s, text: '🔐 AES-256 Frame Decrypted • HD Ready', progress: 85 }));
        }, 2800),
        setTimeout(() => {
          setShieldState(s => ({ ...s, text: '✨ Stream Decrypted • HD Ready', progress: 100 }));
        }, 4400),
        setTimeout(() => {
          setShieldState(s => ({ ...s, active: false }));
        }, 5000)
      );
    } else if (mode === 'seek') {
      setShieldState({
        active: true,
        title: 'KEYFRAME RE-SYNC',
        text: '🟢 Frame Syncing • Decrypting Buffer...',
        progress: 30
      });
      shieldTimersRef.current.push(
        setTimeout(() => {
          setShieldState(s => ({ ...s, text: '⚡ Node ASIA-SOUTH1 Decrypting Stream [1080P]...', progress: 60 }));
        }, 1200),
        setTimeout(() => {
          setShieldState(s => ({ ...s, text: '🔐 AES-256 Keyframe Buffer Decrypted...', progress: 85 }));
        }, 2800),
        setTimeout(() => {
          setShieldState(s => ({ ...s, text: '✨ Stream Synced • HD Ready', progress: 100 }));
        }, 4400),
        setTimeout(() => {
          setShieldState(s => ({ ...s, active: false }));
        }, 5000)
      );
    } else if (mode === 'resume') {
      setShieldState({
        active: true,
        title: 'RESUMING STREAM',
        text: '🟢 Audio Stream Active • Resuming Playback...',
        progress: 30
      });
      shieldTimersRef.current.push(
        setTimeout(() => {
          setShieldState(s => ({ ...s, text: '⚡ Stabilizing CDN Buffer [1080P]...', progress: 60 }));
        }, 1200),
        setTimeout(() => {
          setShieldState(s => ({ ...s, text: '🔐 AES-256 Stream Verified...', progress: 85 }));
        }, 2800),
        setTimeout(() => {
          setShieldState(s => ({ ...s, text: '✨ Playback Active • HD Ready', progress: 100 }));
        }, 4400),
        setTimeout(() => {
          setShieldState(s => ({ ...s, active: false }));
        }, 5000)
      );
    }
  };

  const triggerShield = (type, timeVal) => {
    const isHls = Boolean(
      activeVideo?.hls_url || 
      (activeVideo?.video_id && activeVideo.video_id.includes('.m3u8'))
    );
    // HLS / Native live streams have ZERO YouTube branding, so NEVER show shield!
    if (isHls) {
      clearShieldTimers();
      setShieldState({ active: false, title: '', text: '', progress: 100 });
      waitingPlayRef.current = false;
      return;
    }

    clearShieldTimers();
    currentShieldModeRef.current = type;
    waitingPlayRef.current = true;

    if (type === 'start') {
      setShieldState({
        active: true,
        title: 'DISHA SECURE PROTOCOL',
        text: '📡 Connecting Disha Media Stream (Node #04)...',
        progress: 15
      });
      // Safety fallback: if YouTube fails to send playerState===1 within 6s, start 5s countdown
      shieldTimersRef.current.push(
        setTimeout(() => {
          if (waitingPlayRef.current) {
            waitingPlayRef.current = false;
            startDecryptionCountdown('start');
          }
        }, 6000)
      );
    } else if (type === 'seek') {
      const timeStr = typeof timeVal === 'number' ? formatTime(timeVal) : '';
      setShieldState({
        active: true,
        title: 'KEYFRAME RE-SYNC',
        text: `⚡ Buffering Media Frame ${timeStr ? 'at ' + timeStr : ''}...`,
        progress: 20
      });
      // For seek: if playerState===1 is not received within 1.5s (e.g. already playing), start 5s countdown
      shieldTimersRef.current.push(
        setTimeout(() => {
          if (waitingPlayRef.current) {
            waitingPlayRef.current = false;
            startDecryptionCountdown('seek');
          }
        }, 1500)
      );
    } else if (type === 'resume') {
      setShieldState({
        active: true,
        title: 'RESUMING STREAM',
        text: '⚡ Resuming Secure Stream...',
        progress: 20
      });
      shieldTimersRef.current.push(
        setTimeout(() => {
          if (waitingPlayRef.current) {
            waitingPlayRef.current = false;
            startDecryptionCountdown('resume');
          }
        }, 1500)
      );
    }
  };

  useEffect(() => {
    if (view === 'player' && activeVideo) {
      const isHls = Boolean(
        activeVideo.hls_url || 
        (activeVideo.video_id && activeVideo.video_id.includes('.m3u8'))
      );
      if (!isHls) {
        triggerShield('start');
      } else {
        clearShieldTimers();
        setShieldState({ active: false, title: '', text: '', progress: 100 });
      }
    }
    return () => clearShieldTimers();
  }, [view, activeVideo]);

  // Global instantaneous scroll to top on any navigation or state change
  useEffect(() => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  }, [view, batchTab, folderStack.length, activeVideo?.id, selectedBatch?.id]);

  // Sync fullscreen change across browser / escape / orientation
  useEffect(() => {
    const onFsChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement || document.webkitFullscreenElement));
    };
    document.addEventListener('fullscreenchange', onFsChange);
    document.addEventListener('webkitfullscreenchange', onFsChange);
    return () => {
      document.removeEventListener('fullscreenchange', onFsChange);
      document.removeEventListener('webkitfullscreenchange', onFsChange);
    };
  }, []);

  // Poll time and status from YouTube Iframe + Dynamic Play Detection
  useEffect(() => {
    if (view !== 'player' || !activeVideo) return;
    setCurrentTime(0);
    setDuration(0);
    setIsPlaying(true);

    const handleYTMessage = (e) => {
      try {
        const data = typeof e.data === 'string' ? JSON.parse(e.data) : e.data;
        if (data && data.event === 'infoDelivery' && data.info) {
          if (typeof data.info.currentTime === 'number') {
            setCurrentTime(data.info.currentTime);
          }
          if (typeof data.info.duration === 'number' && data.info.duration > 0) {
            setDuration(data.info.duration);
          }
          if (typeof data.info.playerState === 'number') {
            const isNowPlaying = data.info.playerState === 1;
            setIsPlaying(isNowPlaying);

            // Dynamic Play Trigger: video frames are physically rendering!
            if (isNowPlaying && waitingPlayRef.current) {
              waitingPlayRef.current = false;
              startDecryptionCountdown(currentShieldModeRef.current);
            }
          }
        }
      } catch (err) {}
    };
    window.addEventListener('message', handleYTMessage);

    const interval = setInterval(() => {
      if (iframeRef.current && iframeRef.current.contentWindow) {
        iframeRef.current.contentWindow.postMessage(JSON.stringify({ event: 'listening' }), '*');
      }
    }, 800);

    return () => {
      window.removeEventListener('message', handleYTMessage);
      clearInterval(interval);
    };
  }, [view, activeVideo]);

  // Trigger auto-play on protected Appx player iframe once mounted
  useEffect(() => {
    if (view === 'player' && activeVideo?.embed_player_url) {
      const sendPlay = () => {
        try {
          if (iframeRef.current && iframeRef.current.contentWindow) {
            iframeRef.current.contentWindow.postMessage({ type: 'play', event: 'play' }, '*');
          }
        } catch (e) {}
      };
      sendPlay();
      const t1 = setTimeout(sendPlay, 600);
      const t2 = setTimeout(sendPlay, 1400);
      const t3 = setTimeout(sendPlay, 2500);
      return () => {
        clearTimeout(t1);
        clearTimeout(t2);
        clearTimeout(t3);
      };
    }
  }, [view, activeVideo?.embed_player_url]);

  // Fullscreen / Landscape toggle
  const toggleFullscreen = () => {
    if (!playerContainerRef.current) return;
    if (!document.fullscreenElement && !document.webkitFullscreenElement) {
      if (playerContainerRef.current.requestFullscreen) {
        playerContainerRef.current.requestFullscreen();
      } else if (playerContainerRef.current.webkitRequestFullscreen) {
        playerContainerRef.current.webkitRequestFullscreen();
      }
      setIsFullscreen(true);
      if (window.screen?.orientation?.lock) {
        window.screen.orientation.lock('landscape').catch(() => {});
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen();
      } else if (document.webkitExitFullscreen) {
        document.webkitExitFullscreen();
      }
      setIsFullscreen(false);
      if (window.screen?.orientation?.unlock) {
        window.screen.orientation.unlock();
      }
    }
  };

  // Play / Pause Toggle
  const togglePlayPause = () => {
    const isHls = Boolean(activeVideo?.hls_url || (activeVideo?.video_id && activeVideo.video_id.includes('.m3u8')));
    if (isHls && videoRef.current) {
      if (videoRef.current.paused) {
        videoRef.current.play().catch(() => {});
        setIsPlaying(true);
      } else {
        videoRef.current.pause();
        setIsPlaying(false);
      }
    } else if (iframeRef.current && iframeRef.current.contentWindow) {
      if (isPlaying) {
        iframeRef.current.contentWindow.postMessage(JSON.stringify({ event: 'command', func: 'pauseVideo' }), '*');
        setIsPlaying(false);
      } else {
        iframeRef.current.contentWindow.postMessage(JSON.stringify({ event: 'command', func: 'playVideo' }), '*');
        setIsPlaying(true);
        triggerShield('resume');
      }
    }
  };

  // Timeline Seekbar Drag/Click
  const handleSeek = (e) => {
    const newTime = parseFloat(e.target.value);
    setCurrentTime(newTime);
    const isHls = Boolean(activeVideo?.hls_url || (activeVideo?.video_id && activeVideo.video_id.includes('.m3u8')));
    if (isHls && videoRef.current) {
      videoRef.current.currentTime = newTime;
    } else if (iframeRef.current && iframeRef.current.contentWindow) {
      iframeRef.current.contentWindow.postMessage(JSON.stringify({ event: 'command', func: 'seekTo', args: [newTime, true] }), '*');
      triggerShield('seek', newTime);
    }
  };



  // Smart PDF Opener
  const handleDownloadPdf = (url, key = '') => {
    if (!url) return;
    const keyParam = key ? `&k=${encodeURIComponent(key)}` : '';
    window.open(`${API_BASE_URL}/proxy-pdf?u=${encodeURIComponent(url)}${keyParam}`, '_blank');
  };

  // Speed Controller
  const changeSpeed = (rate) => {
    setPlaybackSpeed(rate);
    if (iframeRef.current && iframeRef.current.contentWindow) {
      iframeRef.current.contentWindow.postMessage(
        JSON.stringify({ event: 'command', func: 'setPlaybackRate', args: [rate] }),
        '*'
      );
    }
    if (videoRef.current) {
      videoRef.current.playbackRate = rate;
    }
    showToast(`स्पीड: ${rate}x`);
  };

  // Seek +/- 10s (Fixed YouTube seekTo)
  const seekRelative = (seconds) => {
    const targetTime = Math.max(0, Math.min(duration || 999999, currentTime + seconds));
    setCurrentTime(targetTime);
    const isHls = Boolean(activeVideo?.hls_url || (activeVideo?.video_id && activeVideo.video_id.includes('.m3u8')));
    if (isHls && videoRef.current) {
      videoRef.current.currentTime = targetTime;
    } else if (iframeRef.current && iframeRef.current.contentWindow) {
      iframeRef.current.contentWindow.postMessage(
        JSON.stringify({ event: 'command', func: 'seekTo', args: [targetTime, true] }),
        '*'
      );
      triggerShield('seek', targetTime);
    }
    showToast(seconds > 0 ? `+${seconds}s आगे` : `${seconds}s पीछे`);
  };

  const showToast = (msg) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3500);
  };

  // 1. Initial Load: Batches & Browser History Sync
  useEffect(() => {
    fetchBatches();

    const handlePopState = (e) => {
      if (e.state) {
        handleNativeBack(e.state);
      }
    };
    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const pushHistory = (state) => {
    window.history.pushState(state, '', window.location.pathname);
  };

  const handleNativeBack = (state) => {
    if (state.view === 'home') {
      setView('home');
      setSelectedBatch(null);
      setActiveVideo(null);
    } else if (state.view === 'batch') {
      setView('batch');
      setActiveVideo(null);
      if (state.folderStack && state.folderStack.length > 0) {
        setFolderStack(state.folderStack);
        const topFolder = state.folderStack[state.folderStack.length - 1];
        if (topFolder) {
          loadFolderContent(state.courseId, topFolder.id);
        }
      }
    }
  };

  const fetchBatches = async () => {
    if (cacheRef.current['batches']) {
      setBatches(cacheRef.current['batches']);
      setLoadingBatches(false);
      return;
    }

    setLoadingBatches(true);
    try {
      const res = await fetch(`${API_BASE_URL}/batches`).then(r => r.json());
      if (res && res.status === 200) {
        cacheRef.current['batches'] = res.batches;
        setBatches(res.batches);
      }
    } catch (err) {
      console.error('Failed to load batches:', err);
    } finally {
      setLoadingBatches(false);
    }
  };

  // 2. Select Batch
  const handleSelectBatch = async (batch) => {
    setSelectedBatch(batch);
    setView('batch');
    // If NCERT book batch (Batch 25), default directly to 'content'
    const defaultTab = batch.id === '25' ? 'content' : 'live';
    setBatchTab(defaultTab);
    setActiveVideo(null);

    // Initial folder stack begins with Root
    setFolderStack([{ id: '-1', title: batch.title }]);
    pushHistory({ view: 'batch', courseId: batch.id, folderStack: [{ id: '-1', title: batch.title }] });

    // Load Overview Data
    const overviewCacheKey = `overview_${batch.id}`;
    if (cacheRef.current[overviewCacheKey]) {
      setOverviewData(cacheRef.current[overviewCacheKey]);
    } else {
      setLoadingOverview(true);
      try {
        const overviewRes = await fetch(`${API_BASE_URL}/batch/${batch.id}/overview`).then(r => r.json());
        if (overviewRes && overviewRes.status === 200) {
          cacheRef.current[overviewCacheKey] = overviewRes;
          setOverviewData(overviewRes);
        }
      } catch (err) {
        console.error('Failed to load overview:', err);
      } finally {
        setLoadingOverview(false);
      }
    }

    // Load Root Folder Contents
    loadFolderContent(batch.id, '-1');
  };

  // 3. Load Folder Content with Instant Cache
  const loadFolderContent = async (courseId, folderId) => {
    const folderCacheKey = `folder_${courseId}_${folderId}`;
    if (cacheRef.current[folderCacheKey]) {
      setFolderItems(cacheRef.current[folderCacheKey]);
      return;
    }

    setLoadingFolder(true);
    try {
      const res = await fetch(`${API_BASE_URL}/batch/${courseId}/folders?parent_id=${folderId}`).then(r => r.json());
      if (res && res.status === 200) {
        cacheRef.current[folderCacheKey] = res.items || [];
        setFolderItems(res.items || []);
      }
    } catch (err) {
      console.error('Failed to load folder:', err);
    } finally {
      setLoadingFolder(false);
    }
  };

  // Open Subfolder
  const handleOpenFolder = (folder) => {
    const nextStack = [...folderStack, { id: folder.id, title: folder.title }];
    setFolderStack(nextStack);
    pushHistory({ view: 'batch', courseId: selectedBatch.id, folderStack: nextStack });
    loadFolderContent(selectedBatch.id, folder.id);
  };

  // Back Button Action
  const handleBack = () => {
    if (view === 'player') {
      // Cleanly exit player back to folder without reload
      setView('batch');
      setActiveVideo(null);
      return;
    }

    if (view === 'batch') {
      if (folderStack.length > 1) {
        // Pop one subfolder
        const nextStack = folderStack.slice(0, folderStack.length - 1);
        setFolderStack(nextStack);
        const parent = nextStack[nextStack.length - 1];
        loadFolderContent(selectedBatch.id, parent.id);
      } else {
        // Return to Batches Home
        setView('home');
        setSelectedBatch(null);
      }
    }
  };

  // Open Video in Dedicated Player Page
  const handlePlayVideo = async (video) => {
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
    if (video.is_upcoming || video.live_status === 2) {
      showToast(`⏰ This live class will start on ${video.date || 'scheduled time'}.`);
      return;
    }

    let playVideo = { ...video };
    // A video is direct YouTube if it has an 11-char ID or ytFlag === 1
    const isDirectYoutube = Boolean(playVideo.video_id && (/^[A-Za-z0-9_-]{11}$/.test(playVideo.video_id) || playVideo.ytFlag === 1));
    const isDirectHls = Boolean(playVideo.hls_url || (playVideo.video_id && playVideo.video_id.includes('.m3u8')));
    
    if (!isDirectYoutube && !isDirectHls && !playVideo.embed_player_url) {
      try {
        const cId = selectedBatch?.id || video.course_id || '62';
        showToast('🔄 Connecting class stream...');
        const vParam = playVideo.video_id ? `?vid=${encodeURIComponent(playVideo.video_id)}` : '';
        const res = await fetch(`${API_BASE_URL}/batch/${cId}/video/${playVideo.id}${vParam}`).then(r => r.json());
        if (res && res.status === 200) {
          let hls = res.hls_url || '';
          if (hls && hls.startsWith('/')) {
            const root = API_BASE_URL.replace(/\/api\/?$/, '');
            hls = `${root}${hls}`;
          }
          let embed = res.embed_player_url || '';
          if (embed && embed.startsWith('/')) {
            const root = API_BASE_URL.replace(/\/api\/?$/, '');
            embed = `${root}${embed}`;
          }
          playVideo.video_id = res.video_id || playVideo.video_id || '';
          playVideo.hls_url = hls || playVideo.hls_url || '';
          playVideo.embed_player_url = embed || playVideo.embed_player_url || '';
          playVideo.ytFlag = res.ytFlag ?? playVideo.ytFlag ?? 0;
          playVideo.player_type = res.player_type || '';
          playVideo.qualities = res.qualities || [];
          if (res.pdf_link) {
            playVideo.pdf_link = res.pdf_link;
            playVideo.pdf_key = res.pdf_key;
            playVideo.is_pdf_encrypted = res.is_pdf_encrypted;
            playVideo.has_notes = true;
          }
        }
      } catch (e) {
        console.error('Failed to resolve video stream:', e);
      }
    }

    const isPlayable = Boolean(
      playVideo.video_id || 
      playVideo.hls_url || 
      playVideo.embed_player_url ||
      (typeof playVideo.video_id === 'string' && playVideo.video_id.includes('.m3u8'))
    );
    if (!isPlayable) {
      showToast(`⚠️ Class stream is currently unavailable.`);
      return;
    }
    setSelectedQuality('Auto');
    setShowQualityMenu(false);
    setShowSpeedMenu(false);
    setActiveVideo(playVideo);
    setView('player');
    pushHistory({ view: 'player', videoId: playVideo.id });
  };

  const activeVideoId = activeVideo?.id;
  const activeHlsUrl = activeVideo?.hls_url;
  const activeM3u8 = activeVideo?.video_id;

  // Quality Switcher for HLS Player
  const switchQuality = (q) => {
    setSelectedQuality(q.quality);
    setShowQualityMenu(false);
    if (!videoRef.current) return;
    const currentTimeSaved = videoRef.current.currentTime;
    const isPausedSaved = videoRef.current.paused;

    let targetUrl = q.url;
    if (targetUrl.startsWith('/api')) {
      const root = API_BASE_URL.replace(/\/api\/?$/, '');
      targetUrl = `${root}${targetUrl}`;
    }

    if (hlsRef.current) {
      hlsRef.current.loadSource(targetUrl);
      hlsRef.current.once(Hls.Events.MANIFEST_PARSED, () => {
        if (videoRef.current) {
          videoRef.current.currentTime = currentTimeSaved;
          if (!isPausedSaved) videoRef.current.play().catch(() => {});
        }
      });
    } else {
      videoRef.current.src = targetUrl;
      videoRef.current.currentTime = currentTimeSaved;
      if (!isPausedSaved) videoRef.current.play().catch(() => {});
    }
    showToast(`क्वालिटी: ${q.quality}`);
  };

  // HLS Player Hook (Handles Live broadcasts and recorded HLS streams)
  useEffect(() => {
    if (view === 'player' && activeVideo) {
      let hlsSource = activeVideo.hls_url || (activeVideo.video_id && activeVideo.video_id.includes('.m3u8') ? activeVideo.video_id : '');
      if (hlsSource) {
        if (hlsSource.startsWith('/api')) {
          const root = API_BASE_URL.replace(/\/api\/?$/, '');
          hlsSource = `${root}${hlsSource}`;
        }
        if (videoRef.current) {
          if (Hls.isSupported()) {
            const hls = new Hls({
              enableWorker: true,
              lowLatencyMode: false,
              backBufferLength: 90,
              maxBufferLength: 30,
              maxMaxBufferLength: 60,
              maxBufferSize: 50 * 1024 * 1024,
              maxBufferHole: 0.5,
              fragLoadingTimeOut: 20000,
              fragLoadingMaxRetry: 5,
              fragLoadingRetryDelay: 1000
            });
            hlsRef.current = hls;
            hls.loadSource(hlsSource);
            hls.attachMedia(videoRef.current);
            hls.on(Hls.Events.MANIFEST_PARSED, () => {
              videoRef.current?.play().catch(() => {});
            });
            let netRetries = 0;
            hls.on(Hls.Events.ERROR, (event, data) => {
              if (data.fatal) {
                switch (data.type) {
                  case Hls.ErrorTypes.NETWORK_ERROR:
                    netRetries++;
                    if (netRetries <= 3) {
                      hls.startLoad();
                    } else {
                      hls.destroy();
                      hlsRef.current = null;
                      if (activeVideo?.embed_player_url) {
                        setActiveVideo(prev => ({ ...prev, hls_url: '' }));
                      }
                    }
                    break;
                  case Hls.ErrorTypes.MEDIA_ERROR:
                    hls.recoverMediaError();
                    break;
                  default:
                    hls.destroy();
                    hlsRef.current = null;
                    if (activeVideo?.embed_player_url) {
                      setActiveVideo(prev => ({ ...prev, hls_url: '' }));
                    }
                    break;
                }
              }
            });
            return () => {
              hls.destroy();
              hlsRef.current = null;
            };
          } else if (videoRef.current.canPlayType('application/vnd.apple.mpegurl')) {
            videoRef.current.src = hlsSource;
            videoRef.current.play().catch(() => {});
          }
        }
      }
    }
  }, [view, activeVideoId, activeHlsUrl, activeM3u8]);

  // Current Title for Top Bar
  const getCurrentTitle = () => {
    if (view === 'player') return activeVideo?.title || 'वीडियो प्लेयर';
    if (view === 'batch') {
      if (folderStack.length > 1) {
        return folderStack[folderStack.length - 1].title;
      }
      return selectedBatch?.title || 'बैच';
    }
    return 'Disha Pro';
  };

  return (
    <div className="min-h-screen bg-black text-white flex justify-center font-sans select-none antialiased">
      {/* Mobile-first centered frame */}
      <div className="w-full max-w-[520px] min-h-screen bg-black border-x border-[#1a1a20] flex flex-col relative">
        
        {/* ========================================================= */}
        {/* TOP BAR: Clean, Minimal, Single Back Button               */}
        {/* ========================================================= */}
        <header className="sticky top-0 z-50 bg-black/95 backdrop-blur-md border-b border-[#1c1c22] px-3.5 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3 min-w-0 flex-1">
            {view !== 'home' && (
              <button 
                onClick={handleBack}
                className="p-1.5 -ml-1.5 rounded-lg text-zinc-300 hover:text-white hover:bg-[#1f1f26] transition-colors shrink-0 active:scale-95"
                title="पीछे जाएं (Back)"
              >
                <ArrowLeft className="w-5 h-5" />
              </button>
            )}

            <div className="min-w-0 flex items-center gap-2">
              <h1 className="font-extrabold text-sm sm:text-base tracking-wide text-white truncate">
                {getCurrentTitle()}
              </h1>
              {view === 'home' && (
                <span className="w-2 h-2 rounded-full bg-emerald-500 shrink-0 shadow-[0_0_8px_rgba(16,185,129,0.7)]"></span>
              )}
            </div>
          </div>
        </header>

        {/* Toast Notification Banner */}
        {toastMessage && (
          <div className="fixed top-16 left-1/2 -translate-x-1/2 z-50 max-w-xs w-full px-4">
            <div className="bg-[#1c1c24] border border-amber-500/40 text-amber-200 text-xs px-3.5 py-2.5 rounded-xl shadow-2xl flex items-center gap-2.5 animate-bounce">
              <AlertCircle className="w-4 h-4 text-amber-400 shrink-0" />
              <span className="leading-snug font-medium">{toastMessage}</span>
            </div>
          </div>
        )}

        {/* ========================================================= */}
        {/* BODY VIEWS                                                */}
        {/* ========================================================= */}
        <main className="flex-1 p-3.5 space-y-4">
          
          {/* ======================================================= */}
          {/* 1. HOME VIEW: BATCHES LIST                              */}
          {/* ======================================================= */}
          {view === 'home' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between px-0.5">
                <span className="text-xs font-bold text-zinc-400 tracking-wider uppercase">
                  My Batches
                </span>
                <span className="text-[11px] font-semibold text-zinc-500">
                  {batches.length} Active Batches
                </span>
              </div>

              {/* Skeleton loading for Batches */}
              {loadingBatches ? (
                <div className="space-y-3">
                  {[1, 2, 3].map(n => (
                    <div key={n} className="bg-[#0f0f13] border border-[#1e1e24] rounded-xl p-3 space-y-3 animate-pulse">
                      <div className="aspect-[16/9] w-full bg-zinc-800/60 rounded-lg"></div>
                      <div className="h-4 bg-zinc-800/80 rounded w-3/4"></div>
                      <div className="h-9 bg-zinc-800/40 rounded w-full"></div>
                    </div>
                  ))}
                </div>
              ) : batches.length === 0 ? (
                <div className="py-12 text-center bg-[#0b0b0e] rounded-xl border border-[#1c1c22] p-4 space-y-3">
                  <div className="w-10 h-10 rounded-full bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center mx-auto">
                    <AlertCircle className="w-5 h-5" />
                  </div>
                  <h4 className="text-xs font-bold text-white">No Active Batches Found</h4>
                  <p className="text-[11px] text-zinc-500 max-w-xs mx-auto">
                    Click the button below to reload session and batches.
                  </p>
                  <button 
                    onClick={() => {
                      delete cacheRef.current['batches'];
                      fetchBatches();
                    }}
                    className="px-4 py-2 rounded-lg text-xs font-bold bg-white text-black hover:bg-zinc-200 transition-colors shadow"
                  >
                    Reload Batches
                  </button>
                </div>
              ) : (
                <div className="space-y-3.5">
                  {batches.map((batch) => (
                    <div 
                      key={batch.id} 
                      className="bg-[#0b0b0e] border border-[#1c1c22] hover:border-zinc-700 rounded-xl overflow-hidden transition-all flex flex-col shadow-lg"
                    >
                      {/* Batch Poster */}
                      <div className="relative aspect-[16/9] w-full bg-zinc-950 overflow-hidden">
                        <img 
                          src={batch.thumbnail} 
                          alt={batch.title} 
                          className="w-full h-full object-cover"
                          onError={(e) => {
                            e.target.src = "https://appx-content-v2.classx.co.in/subject/2026-03-06-0_8425628023565359.png";
                          }}
                        />
                        <div className="absolute top-2.5 left-2.5">
                          <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-black/85 text-emerald-400 border border-emerald-500/30 backdrop-blur-sm">
                            Active • Lifetime
                          </span>
                        </div>
                      </div>

                      {/* Batch Info & Enter Button */}
                      <div className="p-3.5 space-y-3">
                        <h3 className="text-sm font-bold text-white line-clamp-2 leading-snug">
                          {batch.title}
                        </h3>

                        <button 
                          onClick={() => handleSelectBatch(batch)}
                          className="w-full py-2.5 px-4 rounded-lg font-bold text-xs bg-white text-black hover:bg-zinc-200 active:scale-[0.98] transition-all flex items-center justify-center gap-2 shadow"
                        >
                          <Play className="w-3.5 h-3.5 fill-black" />
                          Enter Batch
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ======================================================= */}
          {/* 2. BATCH VIEW (LIVE | CONTENT | TEST)                   */}
          {/* ======================================================= */}
          {view === 'batch' && (
            <div className="space-y-3.5">
              
              {/* Top Segmented Tabs: LIVE | CONTENT | TEST (Sticky at top) */}
              <div className="sticky top-14 z-40 bg-black/95 backdrop-blur-md -mx-3.5 px-3.5 py-2 border-b border-[#1c1c22]">
                <div className="bg-[#111116] p-1 rounded-xl border border-[#202028] flex items-center shadow-lg">
                  <button 
                    onClick={() => {
                      setBatchTab('live');
                      window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
                    }}
                    className={`flex-1 py-2 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
                      batchTab === 'live' 
                        ? 'bg-zinc-800 text-white shadow-md' 
                        : 'text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    <Radio className={`w-3.5 h-3.5 ${batchTab === 'live' ? 'text-red-500' : ''}`} />
                    Live
                  </button>

                  <button 
                    onClick={() => {
                      setBatchTab('content');
                      window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
                    }}
                    className={`flex-1 py-2 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
                      batchTab === 'content' 
                        ? 'bg-zinc-800 text-white shadow-md' 
                        : 'text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    <Folder className="w-3.5 h-3.5 text-amber-400" />
                    Content
                  </button>

                  <button 
                    onClick={() => {
                      setBatchTab('test');
                      window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
                    }}
                    className={`flex-1 py-2 rounded-lg text-xs font-bold flex items-center justify-center gap-1.5 transition-all ${
                      batchTab === 'test' 
                        ? 'bg-zinc-800 text-white shadow-md' 
                        : 'text-zinc-400 hover:text-zinc-200'
                    }`}
                  >
                    <Award className="w-3.5 h-3.5 text-blue-400" />
                    Test
                  </button>
                </div>
              </div>

              {/* ----------------- TAB: LIVE ----------------- */}
              {batchTab === 'live' && (
                <div className="space-y-4">
                  
                  {/* Live Now Section (If active) */}
                  {overviewData.live_classes && overviewData.live_classes.length > 0 && (
                    <div className="space-y-2">
                      <div className="flex items-center gap-2">
                        <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-ping"></span>
                        <span className="text-xs font-bold text-red-400 uppercase tracking-wider">
                          Live Class Running Now
                        </span>
                      </div>

                      {overviewData.live_classes.map((item) => (
                        <div 
                          key={item.id}
                          onClick={() => handlePlayVideo(item)}
                          className="bg-gradient-to-r from-red-950/30 to-[#0e0e14] border border-red-500/40 rounded-xl p-3 flex items-center gap-3 cursor-pointer hover:border-red-400 transition-all active:scale-[0.99]"
                        >
                          <div className="relative w-28 aspect-video rounded-lg overflow-hidden bg-black shrink-0">
                            <img 
                              src={item.thumbnail} 
                              alt={item.title} 
                              className="w-full h-full object-cover"
                            />
                            <div className="absolute top-1 left-1 px-1.5 py-0.5 rounded bg-red-600 text-[9px] font-black uppercase text-white tracking-widest flex items-center gap-1">
                              <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse"></span>
                              LIVE
                            </div>
                          </div>

                          <div className="min-w-0 flex-1">
                            <h4 className="text-xs font-bold text-white line-clamp-2">
                              {item.title}
                            </h4>
                            <p className="text-[10px] text-red-300 font-semibold mt-1">
                              🔴 Watch Live Now
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Upcoming Live Section */}
                  {overviewData.upcoming_classes && overviewData.upcoming_classes.length > 0 && (
                    <div className="space-y-2">
                      <div className="flex items-center gap-1.5">
                        <Clock className="w-3.5 h-3.5 text-amber-400" />
                        <span className="text-xs font-bold text-amber-400 uppercase tracking-wider">
                          Upcoming Classes (Schedule)
                        </span>
                      </div>

                      {overviewData.upcoming_classes.map((item) => (
                        <div 
                          key={item.id}
                          onClick={() => handlePlayVideo(item)}
                          className="bg-[#0f0e13] border border-amber-500/30 hover:border-amber-400/60 rounded-xl p-3 flex items-center gap-3 cursor-pointer transition-all active:scale-[0.99]"
                        >
                          <div className="relative w-28 aspect-video rounded-lg overflow-hidden bg-zinc-900 shrink-0 border border-amber-500/20">
                            <img 
                              src={item.thumbnail} 
                              alt={item.title} 
                              className="w-full h-full object-cover opacity-80"
                            />
                            <div className="absolute top-1 left-1 px-1.5 py-0.5 rounded bg-amber-500 text-[9px] font-black uppercase text-black tracking-wider flex items-center gap-1">
                              <Clock className="w-2.5 h-2.5" />
                              Upcoming
                            </div>
                          </div>

                          <div className="min-w-0 flex-1">
                            <div className="inline-block px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300 border border-amber-500/20 text-[9px] font-bold mb-1">
                              {item.date || 'Scheduled'}
                            </div>
                            <h4 className="text-xs font-bold text-white line-clamp-2 leading-snug">
                              {item.title}
                            </h4>
                            <p className="text-[10px] text-zinc-400 mt-1">
                              Live broadcast will start at scheduled time
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Recent Recorded Lectures */}
                  <div className="space-y-2 pt-1">
                    <span className="text-xs font-bold text-zinc-400 uppercase tracking-wider block">
                      Recent Recorded Lectures
                    </span>

                    {loadingOverview ? (
                      <div className="space-y-2">
                        {[1, 2, 3, 4].map(n => (
                          <div key={n} className="bg-[#0c0c0f] border border-[#1c1c22] rounded-xl p-2.5 flex items-center gap-3 animate-pulse">
                            <div className="w-28 aspect-video bg-zinc-800 rounded-lg shrink-0"></div>
                            <div className="flex-1 space-y-2">
                              <div className="h-3.5 bg-zinc-800 rounded w-4/5"></div>
                              <div className="h-2.5 bg-zinc-800/60 rounded w-1/3"></div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : overviewData.recent_lectures && overviewData.recent_lectures.length > 0 ? (
                      <div className="space-y-2">
                        {overviewData.recent_lectures.map((video) => (
                          <div 
                            key={video.id}
                            onClick={() => handlePlayVideo(video)}
                            className="bg-[#0b0b0e] border border-[#1c1c22] hover:border-zinc-700 rounded-xl p-2.5 flex items-center gap-3 cursor-pointer active:scale-[0.99] transition-all"
                          >
                            <div className="relative w-28 aspect-video rounded-lg overflow-hidden bg-zinc-900 shrink-0">
                              <img 
                                src={video.thumbnail} 
                                alt={video.title} 
                                className="w-full h-full object-cover"
                                onError={(e) => {
                                  e.target.src = "https://appx-content-v2.classx.co.in/subject/2026-03-06-0_8425628023565359.png";
                                }}
                              />
                              <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                                <div className="w-6 h-6 rounded-full bg-white text-black flex items-center justify-center">
                                  <Play className="w-3 h-3 fill-black ml-0.5" />
                                </div>
                              </div>
                            </div>

                            <div className="min-w-0 flex-1">
                              <h4 className="text-xs font-bold text-white line-clamp-2 leading-snug">
                                {video.title}
                              </h4>
                              <div className="text-[10px] text-zinc-500 mt-1.5">
                                <span>{video.date || 'Lecture'}</span>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <div className="py-8 text-center text-zinc-500 text-xs bg-[#0b0b0e] rounded-xl border border-[#1c1c22]">
                        इस बैच में कोई लाइव क्लास उपलब्ध नहीं है। कृपया कंटेंट टैब देखें।
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* ----------------- TAB: CONTENT ----------------- */}
              {batchTab === 'content' && (
                <div className="space-y-2.5">
                  {loadingFolder ? (
                    <div className="space-y-2">
                      {[1, 2, 3, 4, 5].map(n => (
                        <div key={n} className="bg-[#0b0b0e] border border-[#1c1c22] rounded-xl p-3 flex items-center gap-3 animate-pulse">
                          <div className="w-9 h-9 bg-zinc-800 rounded-lg shrink-0"></div>
                          <div className="flex-1 space-y-2">
                            <div className="h-3.5 bg-zinc-800 rounded w-2/3"></div>
                            <div className="h-2.5 bg-zinc-800/50 rounded w-1/4"></div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : folderItems.length === 0 ? (
                    <div className="py-14 text-center bg-[#0b0b0e] rounded-xl border border-[#1c1c22]">
                      <Folder className="w-8 h-8 text-zinc-600 mx-auto mb-2" />
                      <p className="text-xs text-zinc-400">इस फोल्डर में कोई सामग्री उपलब्ध नहीं है</p>
                    </div>
                  ) : (() => {
                    const foldersList = folderItems.filter(i => i.material_type === 'FOLDER');
                    const videosList = folderItems.filter(i => i.material_type === 'VIDEO');
                    const docsList = folderItems.filter(i => i.material_type === 'PDF' || i.material_type === 'FILE');
                    const linksList = folderItems.filter(i => i.material_type === 'LINK');

                    return (
                      <div className="space-y-4">
                        {/* 1. Folders Section */}
                        {foldersList.length > 0 && (
                          <div className="space-y-2">
                            <span className="text-[11px] font-bold text-amber-400 uppercase tracking-wider flex items-center gap-1.5 px-0.5">
                              <Folder className="w-3.5 h-3.5 text-amber-400" />
                              फोल्डर्स ({foldersList.length})
                            </span>
                            <div className="space-y-2">
                              {foldersList.map((item) => (
                                <div 
                                  key={item.id}
                                  onClick={() => handleOpenFolder(item)}
                                  className="bg-[#0b0b0e] hover:bg-[#121217] border border-[#1c1c22] hover:border-zinc-700 rounded-xl p-3 flex items-center justify-between cursor-pointer active:scale-[0.99] transition-all shadow-sm"
                                >
                                  <div className="flex items-center gap-3 min-w-0">
                                    <div className="w-9 h-9 rounded-lg bg-amber-500/10 border border-amber-500/20 text-amber-400 flex items-center justify-center shrink-0">
                                      <Folder className="w-4 h-4" />
                                    </div>
                                    <div className="min-w-0">
                                      <h4 className="text-xs font-bold text-white truncate">
                                        {item.title}
                                      </h4>
                                      <div className="flex items-center gap-2 text-[10px] text-zinc-500 mt-0.5">
                                        {parseInt(item.videos_count) > 0 && <span>{item.videos_count} वीडियो</span>}
                                        {parseInt(item.videos_count) > 0 && parseInt(item.files_count) > 0 && <span>•</span>}
                                        {parseInt(item.files_count) > 0 && <span>{item.files_count} नोट्स</span>}
                                        {parseInt(item.videos_count) === 0 && parseInt(item.files_count) === 0 && <span>फोल्डर</span>}
                                      </div>
                                    </div>
                                  </div>
                                  <ChevronRight className="w-4 h-4 text-zinc-600 shrink-0" />
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* 2. Video Lectures Section */}
                        {videosList.length > 0 && (
                          <div className="space-y-2">
                            <span className="text-[11px] font-bold text-emerald-400 uppercase tracking-wider flex items-center gap-1.5 px-0.5 pt-1">
                              <Play className="w-3.5 h-3.5 text-emerald-400 fill-emerald-400" />
                              क्लास लेक्चर्स ({videosList.length})
                            </span>
                            <div className="space-y-2">
                              {videosList.map((item) => (
                                <div 
                                  key={item.id}
                                  onClick={() => handlePlayVideo(item)}
                                  className="bg-[#0b0b0e] hover:bg-[#121217] border border-[#1c1c22] hover:border-zinc-700 rounded-xl p-2.5 flex items-center gap-3 cursor-pointer active:scale-[0.99] transition-all shadow-sm"
                                >
                                  <div className="relative w-28 aspect-video rounded-lg overflow-hidden bg-zinc-900 shrink-0">
                                    <img 
                                      src={item.thumbnail || "https://appx-content-v2.classx.co.in/subject/2026-03-06-0_8425628023565359.png"} 
                                      alt={item.title} 
                                      className="w-full h-full object-cover"
                                      onError={(e) => {
                                        e.target.src = "https://appx-content-v2.classx.co.in/subject/2026-03-06-0_8425628023565359.png";
                                      }}
                                    />
                                    {item.is_upcoming ? (
                                      <div className="absolute top-1 left-1 px-1.5 py-0.5 rounded bg-amber-500 text-[8px] font-black uppercase text-black">
                                        Upcoming
                                      </div>
                                    ) : (
                                      <div className="absolute inset-0 bg-black/40 flex items-center justify-center">
                                        <div className="w-6 h-6 rounded-full bg-white text-black flex items-center justify-center">
                                          <Play className="w-3 h-3 fill-black ml-0.5" />
                                        </div>
                                      </div>
                                    )}
                                  </div>

                                  <div className="min-w-0 flex-1">
                                    <h4 className="text-xs font-bold text-white line-clamp-2 leading-snug">
                                      {item.title}
                                    </h4>
                                    <div className="text-[10px] text-zinc-500 mt-1.5 flex items-center gap-1.5">
                                      <span>{item.date || (item.is_upcoming ? 'Upcoming Class' : 'Lecture')}</span>
                                      {item.duration && <span>• {item.duration}</span>}
                                    </div>
                                  </div>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* 3. Study Notes & PDFs Section */}
                        {docsList.length > 0 && (
                          <div className="space-y-2">
                            <span className="text-[11px] font-bold text-red-400 uppercase tracking-wider flex items-center gap-1.5 px-0.5 pt-1">
                              <FileText className="w-3.5 h-3.5 text-red-400" />
                              स्टडी नोट्स एवं PDFs ({docsList.length})
                            </span>
                            <div className="space-y-2">
                              {docsList.map((item) => (
                                <div 
                                  key={item.id}
                                  className="bg-[#0b0b0e] border border-[#1c1c22] rounded-xl p-3 flex items-center justify-between"
                                >
                                  <div className="flex items-center gap-3 min-w-0">
                                    <div className="w-9 h-9 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 flex items-center justify-center shrink-0">
                                      <FileText className="w-4 h-4" />
                                    </div>
                                    <div className="min-w-0">
                                      <h4 className="text-xs font-bold text-white truncate">
                                        {item.title}
                                      </h4>
                                      <span className="text-[10px] text-zinc-500">
                                        {item.has_file ? 'अध्ययन सामग्री (PDF)' : 'अपलोड प्रतीक्षारत (Pending Upload)'}
                                      </span>
                                    </div>
                                  </div>

                                  {item.has_file ? (
                                    <a 
                                      href={`${API_BASE_URL}/proxy-pdf?u=${encodeURIComponent(item.pdf_link)}${item.pdf_key ? `&k=${encodeURIComponent(item.pdf_key)}` : ''}`} 
                                      target="_blank" 
                                      rel="noopener noreferrer"
                                      className="p-2 rounded-lg bg-zinc-800 text-zinc-200 hover:text-white transition-colors shrink-0"
                                      title="PDF डाउनलोड करें"
                                    >
                                      <Download className="w-4 h-4" />
                                    </a>
                                  ) : (
                                    <span className="text-[10px] font-semibold text-zinc-600 px-2 py-1 bg-zinc-900 rounded-md">
                                      शीघ्र
                                    </span>
                                  )}
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* 4. External Links Section */}
                        {linksList.length > 0 && (
                          <div className="space-y-2">
                            <span className="text-[11px] font-bold text-blue-400 uppercase tracking-wider flex items-center gap-1.5 px-0.5 pt-1">
                              <ExternalLink className="w-3.5 h-3.5 text-blue-400" />
                              उपयोगी लिंक्स ({linksList.length})
                            </span>
                            <div className="space-y-2">
                              {linksList.map((item) => {
                                let finalLink = item.link_url || '';
                                const tLow = (item.title || '').toLowerCase();
                                if (tLow.includes('telegram') || finalLink.includes('t.me')) {
                                  finalLink = 'https://t.me/hrbseb10thallcorse';
                                } else if (tLow.includes('whatsapp') || finalLink.includes('chat.whatsapp.com') || finalLink.includes('whatsapp.com')) {
                                  finalLink = 'https://whatsapp.com/channel/0029VbF7oDdLo4hdnj39Cw17';
                                }
                                return (
                                  <a 
                                    key={item.id}
                                    href={finalLink}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="bg-[#0b0b0e] hover:bg-[#121217] border border-[#1c1c22] rounded-xl p-3 flex items-center justify-between transition-colors block"
                                  >
                                    <div className="flex items-center gap-3 min-w-0">
                                      <div className="w-9 h-9 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center shrink-0">
                                        <ExternalLink className="w-4 h-4" />
                                      </div>
                                      <div className="min-w-0">
                                        <h4 className="text-xs font-bold text-white truncate">
                                          {item.title}
                                        </h4>
                                        <span className="text-[10px] text-zinc-500">External Link</span>
                                      </div>
                                    </div>
                                    <ChevronRight className="w-4 h-4 text-zinc-600 shrink-0" />
                                  </a>
                                );
                              })}
                            </div>
                          </div>
                        )}
                      </div>
                    );
                  })()}
                </div>
              )}

              {/* ----------------- TAB: TEST ----------------- */}
              {batchTab === 'test' && (
                <div className="bg-[#0b0b0e] border border-[#1c1c22] rounded-xl p-6 text-center space-y-3">
                  <div className="w-10 h-10 rounded-full bg-blue-500/10 border border-blue-500/20 text-blue-400 flex items-center justify-center mx-auto">
                    <Award className="w-5 h-5" />
                  </div>
                  <h4 className="text-xs font-bold text-white">Online Test Series</h4>
                  <p className="text-[11px] text-zinc-500 max-w-xs mx-auto">
                    Test papers and objective quizzes are organized inside the Content folders.
                  </p>
                  <button 
                    onClick={() => setBatchTab('content')}
                    className="px-4 py-2 rounded-lg text-xs font-bold bg-white text-black hover:bg-zinc-200 transition-colors shadow"
                  >
                    View in Content Folder
                  </button>
                </div>
              )}

            </div>
          )}

          {/* ======================================================= */}
          {/* 3. DEDICATED FULL-PAGE VIDEO PLAYER (ZERO CLUTTER)     */}
          {/* ======================================================= */}
          {view === 'player' && activeVideo && (() => {
            const isHls = Boolean(
              activeVideo.hls_url || 
              (activeVideo.video_id && activeVideo.video_id.includes('.m3u8'))
            );
            const isLive = activeVideo.live_status === 1;
            return (
              <div className="space-y-3.5">
                
                {/* 16:9 Cinema Player Screen (Full Landscape Capable) */}
                <div 
                  ref={playerContainerRef}
                  className="relative aspect-video w-full rounded-xl overflow-hidden bg-black border border-[#1e1e24] shadow-2xl flex items-center justify-center group"
                >
                  {/* Floating Exit Fullscreen Button when in Fullscreen */}
                  {isFullscreen && (
                    <button 
                      onClick={toggleFullscreen}
                      className="absolute top-3 right-3 z-50 bg-black/85 hover:bg-black border border-zinc-600 text-white px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-1.5 shadow-2xl backdrop-blur-md active:scale-95 transition-all"
                    >
                      <Minimize2 className="w-4 h-4 text-amber-400" />
                      Exit Fullscreen
                    </button>
                  )}

                  {isHls ? (
                    <div className="relative w-full h-full flex items-center justify-center bg-black group">
                      <video 
                        ref={videoRef}
                        autoPlay 
                        playsInline
                        controls
                        className="w-full h-full object-contain pointer-events-auto"
                        onTimeUpdate={(e) => setCurrentTime(e.target.currentTime)}
                        onLoadedMetadata={(e) => setDuration(e.target.duration || 0)}
                        onPlay={() => setIsPlaying(true)}
                        onPause={() => setIsPlaying(false)}
                      />

                      {/* Top Right Controls Overlay for HLS Player */}
                      {(() => {
                        const tokenMatch = (activeVideo?.hls_url || '').match(/token=([a-zA-Z0-9_-]+)/);
                        const detectedToken = tokenMatch ? tokenMatch[1] : null;
                        const availableQualities = (activeVideo?.qualities && activeVideo.qualities.length > 0)
                          ? activeVideo.qualities
                          : detectedToken
                            ? [
                                { quality: 'Auto', url: `/api/disha/appx-hls/master.m3u8?token=${detectedToken}` },
                                { quality: '720p', url: `/api/disha/appx-hls/720p.m3u8?token=${detectedToken}&q=720p` },
                                { quality: '480p', url: `/api/disha/appx-hls/480p.m3u8?token=${detectedToken}&q=480p` },
                                { quality: '360p', url: `/api/disha/appx-hls/360p.m3u8?token=${detectedToken}&q=360p` }
                              ]
                            : [];

                        return (
                          <div className="absolute top-2.5 right-2.5 z-30 flex items-center gap-1.5 pointer-events-auto">
                            {availableQualities.length > 0 && (
                              <div className="relative">
                                <button
                                  onClick={() => { setShowQualityMenu(!showQualityMenu); setShowSpeedMenu(false); }}
                                  className="px-2.5 py-1 rounded-md bg-black/80 hover:bg-black text-white border border-white/20 text-[11px] font-bold flex items-center gap-1 shadow-lg backdrop-blur transition-all active:scale-95 cursor-pointer"
                                  title="Quality Switcher"
                                >
                                  <Settings className="w-3 h-3 text-emerald-400" />
                                  <span>{selectedQuality}</span>
                                </button>

                                {showQualityMenu && (
                                  <div className="absolute right-0 top-full mt-1.5 w-28 bg-[#121217] border border-[#2b2b36] rounded-lg shadow-2xl py-1 z-40 overflow-hidden backdrop-blur-md">
                                    <div className="px-2.5 py-1 text-[10px] uppercase font-bold text-zinc-400 border-b border-zinc-800">
                                      Quality
                                    </div>
                                    {availableQualities.map((q) => (
                                      <button
                                        key={q.quality}
                                        onClick={() => switchQuality(q)}
                                        className={`w-full text-left px-2.5 py-1.5 text-xs font-semibold flex items-center justify-between transition-colors ${
                                          selectedQuality === q.quality
                                            ? 'bg-emerald-500/20 text-emerald-400'
                                            : 'text-zinc-300 hover:bg-zinc-800 hover:text-white'
                                        }`}
                                      >
                                        <span>{q.quality}</span>
                                        {selectedQuality === q.quality && <Check className="w-3 h-3 text-emerald-400" />}
                                      </button>
                                    ))}
                                  </div>
                                )}
                              </div>
                            )}

                            {/* Speed Selector */}
                            <div className="relative">
                              <button
                                onClick={() => { setShowSpeedMenu(!showSpeedMenu); setShowQualityMenu(false); }}
                                className="px-2.5 py-1 rounded-md bg-black/80 hover:bg-black text-white border border-white/20 text-[11px] font-bold flex items-center gap-1 shadow-lg backdrop-blur transition-all active:scale-95 cursor-pointer"
                                title="Playback Speed"
                              >
                                <Gauge className="w-3 h-3 text-cyan-400" />
                                <span>{playbackSpeed}x</span>
                              </button>

                              {showSpeedMenu && (
                                <div className="absolute right-0 top-full mt-1.5 w-24 bg-[#121217] border border-[#2b2b36] rounded-lg shadow-2xl py-1 z-40 overflow-hidden backdrop-blur-md">
                                  <div className="px-2.5 py-1 text-[10px] uppercase font-bold text-zinc-400 border-b border-zinc-800">
                                    Speed
                                  </div>
                                  {[0.75, 1, 1.25, 1.5, 2].map((rate) => (
                                    <button
                                      key={rate}
                                      onClick={() => {
                                        changeSpeed(rate);
                                        setShowSpeedMenu(false);
                                      }}
                                      className={`w-full text-left px-2.5 py-1.5 text-xs font-semibold flex items-center justify-between transition-colors ${
                                        playbackSpeed === rate
                                          ? 'bg-cyan-500/20 text-cyan-400'
                                          : 'text-zinc-300 hover:bg-zinc-800 hover:text-white'
                                      }`}
                                    >
                                      <span>{rate}x</span>
                                      {playbackSpeed === rate && <Check className="w-3 h-3 text-cyan-400" />}
                                    </button>
                                  ))}
                                </div>
                              )}
                            </div>
                          </div>
                        );
                      })()}
                    </div>
                  ) : activeVideo.embed_player_url ? (
                    <div className="relative w-full h-full flex items-center justify-center bg-black">
                      <iframe 
                        ref={iframeRef}
                        src={activeVideo.embed_player_url}
                        title={activeVideo.title}
                        className="w-full h-full border-0 pointer-events-auto"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; fullscreen"
                        allowFullScreen
                      />
                    </div>
                  ) : (
                    <div className="relative w-full h-full overflow-hidden bg-black flex items-center justify-center">
                      <iframe 
                        ref={iframeRef}
                        src={`https://www.youtube.com/embed/${activeVideo.video_id}?autoplay=1&playsinline=1&rel=0`}
                        title={activeVideo.title}
                        className="w-full h-full border-0 pointer-events-auto"
                        allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share; fullscreen"
                        allowFullScreen
                      />
                    </div>
                  )}
                </div>

                {/* Video Info Card (Title, Date, and Compact Notes) */}
                <div className="bg-[#0b0b0e] border border-[#1c1c22] rounded-xl p-3.5 space-y-3 shadow-lg">
                  <div>
                    <h2 className="text-sm font-bold text-white leading-snug">
                      {activeVideo.title}
                    </h2>
                    <p className="text-[11px] text-zinc-500 mt-1.5 flex items-center gap-1.5">
                      <Clock className="w-3.5 h-3.5 text-zinc-400" />
                      {activeVideo.date || 'Lecture Details'}
                    </p>
                  </div>

                  {activeVideo.has_notes && activeVideo.pdf_link && (
                    <div className="flex items-center justify-between gap-3 pt-2.5 border-t border-zinc-800/80">
                      <div className="flex items-center gap-2 text-xs text-zinc-300 font-medium truncate">
                        <FileText className="w-4 h-4 text-emerald-400 shrink-0" />
                        <span className="truncate">Class Notes PDF</span>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <a 
                          href={`${API_BASE_URL}/proxy-pdf?u=${encodeURIComponent(activeVideo.pdf_link)}${activeVideo.pdf_key ? `&k=${encodeURIComponent(activeVideo.pdf_key)}` : ''}`}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-emerald-500/15 hover:bg-emerald-500/25 border border-emerald-500/30 text-emerald-400 text-xs font-bold transition-all active:scale-95 shadow cursor-pointer"
                        >
                          <ExternalLink className="w-3.5 h-3.5" />
                          <span>Open</span>
                        </a>
                        <a 
                          href={`${API_BASE_URL}/proxy-pdf?u=${encodeURIComponent(activeVideo.pdf_link)}${activeVideo.pdf_key ? `&k=${encodeURIComponent(activeVideo.pdf_key)}` : ''}&download=1`}
                          download="notes.pdf"
                          className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-zinc-800 hover:bg-zinc-700 text-zinc-200 text-xs font-bold transition-all active:scale-95 shadow cursor-pointer"
                        >
                          <Download className="w-3.5 h-3.5" />
                          <span>Download</span>
                        </a>
                      </div>
                    </div>
                  )}
                </div>

              </div>
            );
          })()}

        </main>
      </div>
    </div>
  );
}
