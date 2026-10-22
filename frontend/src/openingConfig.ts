/** Lab identity and delivery assets, independent of the shared Vivacity timeline. */
export type LabOpeningConfig = {
  labId: string;
  labName: string;
  labSubtitle: string;
  /** Prefix for the landscape/portrait and optional lite MP4 encodes. */
  sceneAsset: string;
  landingRoute: string;
  accentColor: string;
  cameraPreset: string;
  version: string;
  homeRootSelector: string;
  homeFocusTarget: string;
};

export const OPENING_TIMELINE = Object.freeze({
  durationSeconds: 7.5,
  handoffStartSeconds: 6.5,
  apertureStartSeconds: 6.98,
  loadGraceMs: 2300,
  decoderStartupDeadlineMs: 5000,
  stalledPlaybackDeadlineMs: 15000,
});

export const ISABELLA_OPENING_CONFIG: Readonly<LabOpeningConfig> = Object.freeze({
  labId: 'isabella',
  labName: 'Isabella Labs',
  labSubtitle: 'By Vivacity',
  sceneAsset: '/vivacity/the-one-isabella',
  landingRoute: '/',
  accentColor: '#c8b69a',
  cameraPreset: 'the-one-isabella',
  version: 'the-one-v1',
  homeRootSelector: '.isabella-home',
  homeFocusTarget: 'isabella-main',
});

export function shouldShowLabOpening(config: LabOpeningConfig, allowDebugReplay = false): boolean {
  if (window.location.pathname !== config.landingRoute ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches) return false;
  const query = new URLSearchParams(window.location.search);
  if (query.get('intro') === 'replay' || (allowDebugReplay && query.has('introDebug'))) return true;
  // The opening is part of each homepage load. Skip only dismisses this instance;
  // a refresh starts a fresh playback without relying on storage state.
  return true;
}

export function openingMediaSource(config: LabOpeningConfig, portrait: boolean, lite: boolean): string {
  return `${config.sceneAsset}-${portrait ? 'portrait' : 'landscape'}${lite ? '-lite' : ''}.mp4`;
}
