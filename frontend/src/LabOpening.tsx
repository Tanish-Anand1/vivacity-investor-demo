import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react';
import { openingMediaSource, OPENING_TIMELINE, type LabOpeningConfig } from './openingConfig';
import './labOpening.css';

export const OPENING_DURATION_MS = OPENING_TIMELINE.durationSeconds * 1000;
const PORTRAIT_QUERY = '(max-aspect-ratio: 4/5)';

export default function LabOpening({ config, finish }: { config: LabOpeningConfig; finish: () => void }) {
  const skip = useRef<HTMLButtonElement>(null);
  const soundButton = useRef<HTMLButtonElement>(null);
  const debugSlider = useRef<HTMLInputElement>(null);
  const opening = useRef<HTMLDivElement>(null);
  const video = useRef<HTMLVideoElement>(null);
  const started = useRef(false);
  const starting = useRef(false);
  const finishTimer = useRef<number | null>(null);
  const finished = useRef(false);
  const mounted = useRef(true);
  const [soundOn, setSoundOn] = useState(false);
  const debug = import.meta.env.DEV && new URLSearchParams(window.location.search).has('introDebug');
  const [media] = useState(() => {
    const portrait = window.matchMedia(PORTRAIT_QUERY).matches;
    const connection = (navigator as Navigator & { connection?: { saveData?: boolean; effectiveType?: string } }).connection;
    const lite = connection?.saveData === true ||
      ['slow-2g', '2g', '3g'].includes(connection?.effectiveType ?? '');
    return { portrait, src: openingMediaSource(config, portrait, lite) };
  });

  const complete = useCallback(() => {
    if (finished.current || !mounted.current) return;
    finished.current = true;
    if (finishTimer.current !== null) window.clearTimeout(finishTimer.current);
    video.current?.pause();
    finish();
  }, [config, finish]);

  useEffect(() => {
    mounted.current = true;
    const previousOverflow = document.body.style.overflow;
    const home = document.querySelector<HTMLElement>(config.homeRootSelector);
    const previouslyInert = home?.hasAttribute('inert');
    const motion = window.matchMedia('(prefers-reduced-motion: reduce)');
    const aspect = window.matchMedia(PORTRAIT_QUERY);
    const element = video.current;
    document.body.style.overflow = 'hidden';
    home?.setAttribute('inert', '');
    skip.current?.focus({ preventScroll: true });

    const key = (event: KeyboardEvent) => {
      if (event.key === 'Escape') { event.preventDefault(); complete(); return; }
      if (event.key !== 'Tab') return;
      const controls = [soundButton.current, skip.current, debugSlider.current].filter(
        (control): control is HTMLButtonElement | HTMLInputElement => control !== null,
      );
      const index = controls.findIndex(control => control === document.activeElement);
      if (index === -1 || (event.shiftKey && index === 0) || (!event.shiftKey && index === controls.length - 1)) {
        event.preventDefault();
        controls[event.shiftKey ? controls.length - 1 : 0]?.focus();
      }
    };
    const changedMotion = () => { if (motion.matches) complete(); };
    // Rotation requires a different authored camera. Finish to the mounted homepage
    // instead of replaying or swapping the shot in the middle of a frame.
    const changedAspect = () => { if (aspect.matches !== media.portrait) complete(); };
    document.addEventListener('keydown', key);
    motion.addEventListener('change', changedMotion);
    aspect.addEventListener('change', changedAspect);

    const startupDeadline = performance.now() + OPENING_TIMELINE.decoderStartupDeadlineMs;
    let loadGrace = window.setTimeout(() => {
      if (started.current) return;
      // Metadata confirms that delivery has begun. A cold decoder gets bounded
      // time to produce its first frame; an unavailable download still exits fast.
      const remaining = startupDeadline - performance.now();
      if (element && element.readyState >= HTMLMediaElement.HAVE_METADATA && !element.error && remaining > 0) {
        loadGrace = window.setTimeout(() => { if (!started.current) complete(); }, remaining);
      } else complete();
    }, OPENING_TIMELINE.loadGraceMs);
    let frame = 0;
    let videoFrame = 0;
    const setAperture = (elapsed: number) => {
      const progress = Math.max(0, Math.min(1,
        (elapsed - OPENING_TIMELINE.apertureStartSeconds) /
        (OPENING_TIMELINE.durationSeconds - OPENING_TIMELINE.apertureStartSeconds),
      ));
      // Reveal the real homepage through the same central opening as the film.
      // Seeking backward resets the mask for production review.
      opening.current?.style.setProperty('--opening-aperture', `${50 * progress}%`);
    };
    if (element && 'requestVideoFrameCallback' in element) {
      const syncVideo = (_now: DOMHighResTimeStamp, metadata: VideoFrameCallbackMetadata) => {
        setAperture(metadata.mediaTime);
        videoFrame = element.requestVideoFrameCallback(syncVideo);
      };
      videoFrame = element.requestVideoFrameCallback(syncVideo);
    } else {
      const syncFallback = () => {
        setAperture(video.current?.currentTime ?? 0);
        frame = requestAnimationFrame(syncFallback);
      };
      frame = requestAnimationFrame(syncFallback);
    }
    if (motion.matches) complete();

    return () => {
      mounted.current = false;
      window.clearTimeout(loadGrace);
      if (finishTimer.current !== null) window.clearTimeout(finishTimer.current);
      cancelAnimationFrame(frame);
      if (videoFrame) element?.cancelVideoFrameCallback(videoFrame);
      element?.pause();
      document.body.style.overflow = previousOverflow;
      if (!previouslyInert) home?.removeAttribute('inert');
      document.removeEventListener('keydown', key);
      motion.removeEventListener('change', changedMotion);
      aspect.removeEventListener('change', changedAspect);
    };
  }, [complete, config.homeRootSelector, debug, media.portrait]);

  const play = async () => {
    const element = video.current;
    if (!element || finished.current || starting.current || started.current) return;
    starting.current = true;
    try {
      await element.play();
      if (finished.current || !mounted.current) { element.pause(); return; }
      started.current = true;
      // Media time owns the exact ending; wall time only protects a stalled decoder.
      if (!debug) finishTimer.current = window.setTimeout(complete, OPENING_TIMELINE.stalledPlaybackDeadlineMs);
    } catch { complete(); }
    finally { starting.current = false; }
  };

  const toggleSound = () => {
    const element = video.current;
    if (!element) return;
    const next = !soundOn;
    element.muted = !next;
    setSoundOn(next);
    if (next && started.current && element.paused) {
      element.play().catch(() => {
        element.muted = true;
        if (mounted.current) setSoundOn(false);
      });
    }
  };

  return <div ref={opening} className="lab-opening" role="dialog" aria-modal="true"
    aria-label={`${config.labName} introduction`} data-frame-format={media.portrait ? 'portrait' : 'landscape'}
    style={{ '--opening-accent': config.accentColor } as CSSProperties}>
    <video ref={video} className="lab-opening-video" muted playsInline preload="auto" aria-hidden="true"
      src={media.src} onLoadedMetadata={play} onCanPlay={play} onError={complete} onEnded={complete} />
    <div className="lab-opening-controls">
      <button ref={soundButton} className="lab-opening-control" type="button" onClick={toggleSound} aria-pressed={soundOn}>
        {soundOn ? 'Sound on' : 'Sound off'}
      </button>
      <button ref={skip} className="lab-opening-control" type="button" onClick={complete}>Skip intro <span aria-hidden="true">↗</span></button>
    </div>
    {debug && <label className="lab-opening-debug">Film time <input ref={debugSlider} type="range" min="0"
      max={OPENING_TIMELINE.durationSeconds} step="0.01" defaultValue="0" onChange={event => {
        if (video.current) { video.current.pause(); video.current.currentTime = Number(event.target.value); }
      }} /></label>}
  </div>;
}
