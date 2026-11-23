import React, { useEffect, useRef, useState, useCallback } from 'react';
import Hls from 'hls.js';
import {
  Play,
  Pause,
  RotateCcw,
  RotateCw,
  Volume2,
  VolumeX,
  Maximize,
  Minimize,
  Settings,
  Gauge,
  Check,
  ArrowLeft,
  Tv
} from 'lucide-react';

function formatTime(seconds) {
  if (!seconds || isNaN(seconds) || seconds < 0) return '00:00';
  const s = Math.floor(seconds);
  const m = Math.floor(s / 60);
  const h = Math.floor(m / 60);
  const remM = m % 60;
  const remS = s % 60;
  if (h > 0) {
    return `${String(h).padStart(2, '0')}:${String(remM).padStart(2, '0')}:${String(remS).padStart(2, '0')}`;
  }
  return `${String(remM).padStart(2, '0')}:${String(remS).padStart(2, '0')}`;
}

const SPEED_OPTIONS = [0.5, 0.75, 1, 1.25, 1.5, 2];
const SCREEN_FITS = ['contain', 'cover', 'fill'];
const FIT_LABELS = { contain: 'Fit', cover: 'Zoom', fill: 'Stretch' };

export default function CustomVideoPlayer({
  src,
  qualities = [],
  title = '',
  onBack,
  autoPlay = true,
}) {
  const containerRef = useRef(null);
  const videoRef = useRef(null);
  const hlsRef = useRef(null);
  const hideTimerRef = useRef(null);
  const lastTapRef = useRef(0);
  const lastTapXRef = useRef(0);

  const [playing, setPlaying] = useState(false);
  const [buffering, setBuffering] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [bufferedTime, setBufferedTime] = useState(0);
  const [volume, setVolume] = useState(1);
  const [muted, setMuted] = useState(false);
  const [speed, setSpeed] = useState(1);
  const [selectedQuality, setSelectedQuality] = useState('Auto');
  const [availableQualities, setAvailableQualities] = useState([]);
  const [screenFit, setScreenFit] = useState('contain');
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [controlsVisible, setControlsVisible] = useState(true);
  const [activePopup, setActivePopup] = useState('none'); // 'none' | 'speed' | 'quality'
  const [centerRipple, setCenterRipple] = useState(null); // { type: 'rewind'|'forward'|'play'|'pause', key: number }

  // Auto-hide controls timer
  const resetHideTimer = useCallback(() => {
    setControlsVisible(true);
    if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    hideTimerRef.current = setTimeout(() => {
      setControlsVisible(false);
      setActivePopup('none');
    }, 3200);
  }, []);

  const showControlsPermanently = useCallback(() => {
    setControlsVisible(true);
    if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
  }, []);

  // Whenever playback pauses or ends, keep controls visible
  useEffect(() => {
    if (!playing) {
      showControlsPermanently();
    } else {
      resetHideTimer();
    }
  }, [playing, resetHideTimer, showControlsPermanently]);

  // Fullscreen listener
  useEffect(() => {
    const handleFsChange = () => {
      const isFs = Boolean(document.fullscreenElement || document.webkitFullscreenElement);
      setIsFullscreen(isFs);
      if (!isFs) {
        try {
          if (screen.orientation && screen.orientation.unlock) {
            screen.orientation.unlock();
          }
        } catch (e) {}
      }
    };
    document.addEventListener('fullscreenchange', handleFsChange);
    document.addEventListener('webkitfullscreenchange', handleFsChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFsChange);
      document.removeEventListener('webkitfullscreenchange', handleFsChange);
      if (hideTimerRef.current) clearTimeout(hideTimerRef.current);
    };
  }, []);

  // Initialize HLS or Native Video
  useEffect(() => {
    const video = videoRef.current;
    if (!video || !src) return;

    setBuffering(true);
    setCurrentTime(0);

    if (hlsRef.current) {
      try {
        hlsRef.current.destroy();
      } catch (e) {}
      hlsRef.current = null;
    }

    const isHls = /\.m3u8(\?|$)/i.test(src) || src.includes('appx-hls');

    if (isHls && Hls.isSupported()) {
      const hls = new Hls({
        enableWorker: false,
        lowLatencyMode: false,
        autoStartLoad: true,
        maxBufferLength: 20,
        maxMaxBufferLength: 50,
      });
      hlsRef.current = hls;

      hls.loadSource(src);
      hls.attachMedia(video);

      hls.on(Hls.Events.MANIFEST_PARSED, (_event, data) => {
        setBuffering(false);
        if (data && data.levels && data.levels.length > 0) {
          const heights = Array.from(
            new Set(
              data.levels
                .map((l) => l.height)
                .filter((h) => Boolean(h && h > 0))
                .sort((a, b) => b - a)
                .map((h) => `${h}p`)
            )
          );
          if (heights.length > 0) {
            setAvailableQualities(['Auto', ...heights]);
          }
        }
        if (autoPlay) {
          video.play().catch(() => {});
        }
      });

      hls.on(Hls.Events.FRAG_BUFFERED, () => {
        setBuffering(false);
      });

      hls.on(Hls.Events.ERROR, (_event, data) => {
        if (data.fatal) {
          if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
            hls.startLoad();
          } else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
            hls.recoverMediaError();
          } else {
            setBuffering(false);
          }
        }
      });
    } else if (video.canPlayType('application/vnd.apple.mpegurl') || !isHls) {
      video.src = src;
      video.load();
      if (autoPlay) {
        video.play().catch(() => {});
      }
    }

    // Populate fallback qualities from prop if available
    if (qualities && qualities.length > 0) {
      const qLabels = qualities.map((q) => q.quality || q.label || '720p');
      if (!qLabels.includes('Auto')) qLabels.unshift('Auto');
      setAvailableQualities(qLabels);
    }

    return () => {
      if (hlsRef.current) {
        try {
          hlsRef.current.destroy();
        } catch (e) {}
        hlsRef.current = null;
      }
    };
  }, [src, autoPlay, qualities]);

  // Handle Play/Pause
  const togglePlay = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused || video.ended) {
      video.play().catch(() => {});
      triggerRipple('play');
    } else {
      video.pause();
      triggerRipple('pause');
    }
  };

  const triggerRipple = (type) => {
    setCenterRipple({ type, key: Date.now() });
    setTimeout(() => setCenterRipple(null), 650);
  };

  // Handle Double-tap / Single-tap on screen
  const handleScreenTouch = (e) => {
    const now = Date.now();
    const touch = e.changedTouches ? e.changedTouches[0] : e;
    const clientX = touch.clientX;
    const rect = containerRef.current?.getBoundingClientRect();

    if (now - lastTapRef.current < 300) {
      // Double tap detected
      if (rect) {
        const xPos = clientX - rect.left;
        const width = rect.width;
        if (xPos < width * 0.4) {
          skip(-10);
          triggerRipple('rewind');
        } else if (xPos > width * 0.6) {
          skip(10);
          triggerRipple('forward');
        } else {
          togglePlay();
        }
      }
      lastTapRef.current = 0;
      return;
    }

    lastTapRef.current = now;
    lastTapXRef.current = clientX;

    // Toggle controls visibility on single tap
    if (controlsVisible) {
      if (activePopup !== 'none') {
        setActivePopup('none');
      } else {
        setControlsVisible(false);
      }
    } else {
      resetHideTimer();
    }
  };

  // Seek / Skip
  const skip = (seconds) => {
    const video = videoRef.current;
    if (!video) return;
    const newTime = Math.max(0, Math.min(video.duration || duration || 0, video.currentTime + seconds));
    video.currentTime = newTime;
    setCurrentTime(newTime);
    resetHideTimer();
  };

  const handleSeek = (e) => {
    const video = videoRef.current;
    if (!video) return;
    const val = Number(e.target.value);
    video.currentTime = val;
    setCurrentTime(val);
    resetHideTimer();
  };

  // Change Speed
  const handleSpeedSelect = (s) => {
    const video = videoRef.current;
    if (video) video.playbackRate = s;
    setSpeed(s);
    setActivePopup('none');
    resetHideTimer();
  };

  // Change Quality
  const handleQualitySelect = (qLabel) => {
    setSelectedQuality(qLabel);
    setActivePopup('none');
    resetHideTimer();

    // 1. If HLS.js is running, switch level
    if (hlsRef.current && hlsRef.current.levels && hlsRef.current.levels.length > 0) {
      if (qLabel === 'Auto') {
        hlsRef.current.currentLevel = -1;
      } else {
        const targetHeight = parseInt(qLabel.replace(/\D+/g, ''), 10);
        let bestIdx = 0;
        let minDiff = 99999;
        hlsRef.current.levels.forEach((lvl, idx) => {
          const diff = Math.abs((lvl.height || 0) - targetHeight);
          if (diff < minDiff) {
            minDiff = diff;
            bestIdx = idx;
          }
        });
        hlsRef.current.currentLevel = bestIdx;
      }
      return;
    }

    // 2. Fallback: match URL in qualities list
    const matched = qualities.find((q) => (q.quality || q.label) === qLabel);
    if (matched && matched.url && matched.url !== src && videoRef.current) {
      const cur = videoRef.current.currentTime;
      videoRef.current.src = matched.url;
      videoRef.current.currentTime = cur;
      videoRef.current.play().catch(() => {});
    }
  };

  // Cycle Screen Fit
  const cycleFit = () => {
    const curIdx = SCREEN_FITS.indexOf(screenFit);
    const next = SCREEN_FITS[(curIdx + 1) % SCREEN_FITS.length];
    setScreenFit(next);
    resetHideTimer();
  };

  // Fullscreen toggle
  const toggleFullscreen = async () => {
    const container = containerRef.current;
    if (!container) return;

    try {
      if (!document.fullscreenElement && !document.webkitFullscreenElement) {
        if (container.requestFullscreen) {
          await container.requestFullscreen();
        } else if (container.webkitRequestFullscreen) {
          container.webkitRequestFullscreen();
        }
        setIsFullscreen(true);
        try {
          if (screen.orientation && screen.orientation.lock) {
            await screen.orientation.lock('landscape').catch(() => {});
          }
        } catch (e) {}
      } else {
        if (document.exitFullscreen) {
          await document.exitFullscreen();
        } else if (document.webkitExitFullscreen) {
          document.webkitExitFullscreen();
        }
        setIsFullscreen(false);
        try {
          if (screen.orientation && screen.orientation.unlock) {
            screen.orientation.unlock();
          }
        } catch (e) {}
      }
    } catch (e) {
      setIsFullscreen(!isFullscreen);
    }
    resetHideTimer();
  };

  // Progress Bar percentage calculation
  const progressPercent = duration > 0 ? (currentTime / duration) * 100 : 0;
  const bufferPercent = duration > 0 ? (bufferedTime / duration) * 100 : 0;

  return (
    <div
      ref={containerRef}
      onMouseMove={resetHideTimer}
      onClick={handleScreenTouch}
      className="relative w-full aspect-video bg-black rounded-xl overflow-hidden select-none group touch-none border border-zinc-900 shadow-2xl flex items-center justify-center"
      style={{ WebkitTapHighlightColor: 'transparent' }}
    >
      {/* Video Element */}
      <video
        ref={videoRef}
        playsInline
        autoPlay={autoPlay}
        style={{ objectFit: screenFit }}
        className="w-full h-full bg-black cursor-pointer"
        onPlay={() => setPlaying(true)}
        onPause={() => setPlaying(false)}
        onWaiting={() => setBuffering(true)}
        onPlaying={() => setBuffering(false)}
        onCanPlay={() => setBuffering(false)}
        onTimeUpdate={(e) => {
          const v = e.target;
          setCurrentTime(v.currentTime);
          if (v.buffered.length > 0) {
            setBufferedTime(v.buffered.end(v.buffered.length - 1));
          }
        }}
        onLoadedMetadata={(e) => {
          setDuration(e.target.duration || 0);
          setBuffering(false);
        }}
      />

      {/* Buffering Spinner */}
      {buffering && (
        <div className="absolute inset-0 z-20 flex flex-col items-center justify-center bg-black/40 pointer-events-none backdrop-blur-[2px]">
          <div className="w-11 h-11 rounded-full border-4 border-white/20 border-t-emerald-400 animate-spin" />
          <span className="text-[11px] font-bold text-white/90 mt-2.5 drop-shadow">Loading stream...</span>
        </div>
      )}

      {/* Animated Center Ripple (Rewind / Forward / Play / Pause) */}
      {centerRipple && (
        <div className="absolute inset-0 z-25 flex items-center justify-center pointer-events-none">
          <div className="p-4 rounded-full bg-black/70 backdrop-blur-md text-white border border-white/20 animate-ping">
            {centerRipple.type === 'rewind' && (
              <div className="flex items-center gap-1 font-bold text-sm">
                <RotateCcw className="w-6 h-6 text-emerald-400" />
                <span>-10s</span>
              </div>
            )}
            {centerRipple.type === 'forward' && (
              <div className="flex items-center gap-1 font-bold text-sm">
                <span>+10s</span>
                <RotateCw className="w-6 h-6 text-emerald-400" />
              </div>
            )}
            {centerRipple.type === 'play' && <Play className="w-8 h-8 fill-emerald-400 text-emerald-400" />}
            {centerRipple.type === 'pause' && <Pause className="w-8 h-8 fill-white text-white" />}
          </div>
        </div>
      )}

      {/* ========================================================= */}
      {/* 1. TOP OVERLAY BAR (Auto-hiding, smoothly transitions)    */}
      {/* ========================================================= */}
      <div
        onClick={(e) => e.stopPropagation()}
        className={`absolute top-0 left-0 right-0 px-3.5 py-3 bg-gradient-to-b from-black/90 via-black/50 to-transparent z-30 flex items-center justify-between gap-3 transition-opacity duration-300 ${
          controlsVisible ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        }`}
      >
        {/* Left: Back button + Title */}
        <div className="flex items-center gap-2.5 min-w-0">
          {onBack && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                if (isFullscreen || document.fullscreenElement || document.webkitFullscreenElement) {
                  toggleFullscreen();
                  return;
                }
                onBack();
              }}
              className="p-1.5 rounded-full bg-white/10 hover:bg-white/20 text-white cursor-pointer active:scale-95 transition-all"
              title="Back"
            >
              <ArrowLeft className="w-4 h-4" />
            </button>
          )}
          <span className="text-xs sm:text-sm font-bold text-white drop-shadow truncate">
            {title || 'Playing Video'}
          </span>
        </div>

        {/* Right: Screen Fit + Quality Indicator */}
        <div className="flex items-center gap-2 shrink-0">
          <button
            onClick={(e) => {
              e.stopPropagation();
              cycleFit();
            }}
            className="px-2.5 py-1 rounded-md bg-white/10 hover:bg-white/20 text-white text-[10px] font-bold border border-white/15 flex items-center gap-1 cursor-pointer transition-all active:scale-95"
            title="Screen Fit Mode (Fit, Zoom, Stretch)"
          >
            <Tv className="w-3 h-3 text-emerald-400" />
            <span>{FIT_LABELS[screenFit]}</span>
          </button>
        </div>
      </div>

      {/* ========================================================= */}
      {/* 2. CENTER PLAY / PAUSE BUTTON (Auto-hiding overlay)       */}
      {/* ========================================================= */}
      <div
        onClick={(e) => {
          e.stopPropagation();
          togglePlay();
        }}
        className={`absolute inset-0 flex items-center justify-center z-25 transition-opacity duration-300 cursor-pointer ${
          controlsVisible && !buffering ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        }`}
      >
        <div className="p-3.5 rounded-full bg-black/60 hover:bg-black/80 text-white border border-white/20 backdrop-blur-md shadow-2xl active:scale-90 transition-transform">
          {playing ? (
            <Pause className="w-7 h-7 sm:w-8 sm:h-8 fill-white" />
          ) : (
            <Play className="w-7 h-7 sm:w-8 sm:h-8 fill-white translate-x-0.5" />
          )}
        </div>
      </div>

      {/* ========================================================= */}
      {/* 3. SPEED & QUALITY POPUPS (Floating Above Bottom Bar)     */}
      {/* ========================================================= */}
      {activePopup === 'speed' && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="absolute bottom-16 right-16 z-40 bg-[#121217]/95 border border-zinc-700/80 rounded-xl shadow-2xl py-1.5 w-28 backdrop-blur-lg overflow-hidden"
        >
          <div className="px-3 py-1 text-[10px] uppercase font-bold text-zinc-400 border-b border-zinc-800">
            Speed
          </div>
          {SPEED_OPTIONS.map((rate) => (
            <button
              key={rate}
              onClick={() => handleSpeedSelect(rate)}
              className={`w-full px-3 py-1.5 text-xs font-semibold flex items-center justify-between text-left transition-colors cursor-pointer ${
                speed === rate ? 'bg-emerald-500/20 text-emerald-400' : 'text-zinc-300 hover:bg-zinc-800'
              }`}
            >
              <span>{rate}x</span>
              {speed === rate && <Check className="w-3.5 h-3.5 text-emerald-400" />}
            </button>
          ))}
        </div>
      )}

      {activePopup === 'quality' && (
        <div
          onClick={(e) => e.stopPropagation()}
          className="absolute bottom-16 right-8 z-40 bg-[#121217]/95 border border-zinc-700/80 rounded-xl shadow-2xl py-1.5 w-32 backdrop-blur-lg overflow-hidden max-h-48 overflow-y-auto"
        >
          <div className="px-3 py-1 text-[10px] uppercase font-bold text-zinc-400 border-b border-zinc-800">
            Quality
          </div>
          {availableQualities.length > 0 ? (
            availableQualities.map((q) => (
              <button
                key={q}
                onClick={() => handleQualitySelect(q)}
                className={`w-full px-3 py-1.5 text-xs font-semibold flex items-center justify-between text-left transition-colors cursor-pointer ${
                  selectedQuality === q ? 'bg-emerald-500/20 text-emerald-400' : 'text-zinc-300 hover:bg-zinc-800'
                }`}
              >
                <span>{q}</span>
                {selectedQuality === q && <Check className="w-3.5 h-3.5 text-emerald-400" />}
              </button>
            ))
          ) : (
            <div className="px-3 py-2 text-[11px] text-zinc-500">Auto Only</div>
          )}
        </div>
      )}

      {/* ========================================================= */}
      {/* 4. BOTTOM CONTROLS BAR (Auto-hiding, smoothly transitions)*/}
      {/* ========================================================= */}
      <div
        onClick={(e) => e.stopPropagation()}
        className={`absolute bottom-0 left-0 right-0 px-3.5 pb-2.5 pt-4 bg-gradient-to-t from-black/95 via-black/75 to-transparent z-30 transition-opacity duration-300 flex flex-col gap-1.5 ${
          controlsVisible ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none'
        }`}
      >
        {/* Row 1: Interactive Seekbar */}
        <div className="relative w-full h-3 flex items-center cursor-pointer group/seek">
          {/* Track Background */}
          <div className="relative w-full h-1 group-hover/seek:h-1.5 rounded-full bg-white/20 transition-all overflow-hidden">
            {/* Buffer bar */}
            <div
              className="absolute inset-y-0 left-0 bg-white/30 rounded-full transition-all"
              style={{ width: `${Math.min(100, bufferPercent)}%` }}
            />
            {/* Played gradient bar */}
            <div
              className="absolute inset-y-0 left-0 bg-gradient-to-r from-emerald-500 to-teal-400 rounded-full"
              style={{ width: `${Math.min(100, progressPercent)}%` }}
            />
          </div>

          {/* Range Slider for drag & click */}
          <input
            type="range"
            min={0}
            max={duration > 0 ? duration : 100}
            step={0.25}
            value={currentTime}
            onChange={handleSeek}
            className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
          />

          {/* Thumb indicator */}
          <div
            className="pointer-events-none absolute w-3 h-3 rounded-full bg-white shadow-lg transition-transform -translate-x-1/2 scale-0 group-hover/seek:scale-100"
            style={{ left: `${Math.min(100, progressPercent)}%` }}
          />
        </div>

        {/* Row 2: Transport Buttons + Time + Speed/Quality/Fullscreen */}
        <div className="flex items-center justify-between text-white text-xs pt-0.5">
          {/* Left: Play/Pause, -10s, +10s, Time */}
          <div className="flex items-center gap-2 sm:gap-3">
            <button
              onClick={togglePlay}
              className="p-1 rounded-md hover:bg-white/10 active:scale-95 transition-all text-white cursor-pointer"
              title={playing ? 'Pause' : 'Play'}
            >
              {playing ? <Pause className="w-4 h-4 fill-white" /> : <Play className="w-4 h-4 fill-white" />}
            </button>

            <button
              onClick={() => skip(-10)}
              className="relative p-1 rounded-md hover:bg-white/10 active:scale-95 transition-all text-white cursor-pointer"
              title="Rewind 10s"
            >
              <RotateCcw className="w-4 h-4" />
              <span className="absolute inset-0 flex items-center justify-center text-[7px] font-black mt-0.5">10</span>
            </button>

            <button
              onClick={() => skip(10)}
              className="relative p-1 rounded-md hover:bg-white/10 active:scale-95 transition-all text-white cursor-pointer"
              title="Forward 10s"
            >
              <RotateCw className="w-4 h-4" />
              <span className="absolute inset-0 flex items-center justify-center text-[7px] font-black mt-0.5">10</span>
            </button>

            {/* Elapsed / Total Time */}
            <span className="text-[11px] font-bold text-zinc-300 font-mono tracking-tight ml-1">
              {formatTime(currentTime)} / {formatTime(duration)}
            </span>
          </div>

          {/* Right: Speed, Quality, Fullscreen */}
          <div className="flex items-center gap-1 sm:gap-2">
            {/* Speed Popover Trigger */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                setActivePopup(activePopup === 'speed' ? 'none' : 'speed');
              }}
              className="px-2 py-1 rounded-md hover:bg-white/10 text-[11px] font-bold text-zinc-300 hover:text-white flex items-center gap-1 transition-all cursor-pointer"
              title="Playback Speed"
            >
              <Gauge className="w-3.5 h-3.5 text-cyan-400" />
              <span>{speed}x</span>
            </button>

            {/* Quality Popover Trigger */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                setActivePopup(activePopup === 'quality' ? 'none' : 'quality');
              }}
              className="px-2 py-1 rounded-md hover:bg-white/10 text-[11px] font-bold text-zinc-300 hover:text-white flex items-center gap-1 transition-all cursor-pointer"
              title="Video Quality"
            >
              <Settings className="w-3.5 h-3.5 text-emerald-400" />
              <span>{selectedQuality}</span>
            </button>

            {/* Fullscreen Toggle */}
            <button
              onClick={(e) => {
                e.stopPropagation();
                toggleFullscreen();
              }}
              className="p-1 rounded-md hover:bg-white/10 text-zinc-300 hover:text-white active:scale-95 transition-all cursor-pointer"
              title={isFullscreen ? 'Exit Fullscreen' : 'Fullscreen'}
            >
              {isFullscreen ? <Minimize className="w-4 h-4" /> : <Maximize className="w-4 h-4" />}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
