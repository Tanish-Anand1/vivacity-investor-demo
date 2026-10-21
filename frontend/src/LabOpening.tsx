import {useCallback,useEffect,useRef,useState} from 'react';
import './labOpening.css';

export const OPENING_DURATION_MS=7500;
const LOAD_GRACE_MS=2300;

export default function LabOpening({finish}:{finish:()=>void}){
 const skip=useRef<HTMLButtonElement>(null);
 const soundButton=useRef<HTMLButtonElement>(null);
 const opening=useRef<HTMLDivElement>(null);
 const video=useRef<HTMLVideoElement>(null);
 const startedAt=useRef<number|null>(null);
 const starting=useRef(false);
 const finishTimer=useRef<number|null>(null);
 const finished=useRef(false);
 const [soundOn,setSoundOn]=useState(false);
 const debug=import.meta.env.DEV&&new URLSearchParams(window.location.search).has('introDebug');
 const portrait=window.matchMedia('(max-aspect-ratio: 4/5)').matches;
 const connection=(navigator as Navigator&{connection?:{saveData?:boolean;effectiveType?:string}}).connection;
 const lite=(portrait&&window.innerWidth<=600)||connection?.saveData===true||['slow-2g','2g','3g'].includes(connection?.effectiveType??'');
 const format=portrait?'portrait':'landscape';
 const complete=useCallback(()=>{if(finished.current)return;finished.current=true;if(finishTimer.current!==null)window.clearTimeout(finishTimer.current);video.current?.pause();finish();},[finish]);

 useEffect(()=>{
  const previousOverflow=document.body.style.overflow;
  const home=document.querySelector<HTMLElement>('.isabella-home');
  const motion=window.matchMedia('(prefers-reduced-motion: reduce)');
  document.body.style.overflow='hidden';home?.setAttribute('inert','');skip.current?.focus();
  const key=(event:KeyboardEvent)=>{
   if(event.key==='Escape'){event.preventDefault();complete();return;}
   if(event.key!=='Tab')return;
   if(event.shiftKey&&document.activeElement===soundButton.current){event.preventDefault();skip.current?.focus();}
   else if(!event.shiftKey&&document.activeElement===skip.current){event.preventDefault();soundButton.current?.focus();}
  };
  const changed=()=>{if(motion.matches)complete();};
  document.addEventListener('keydown',key);motion.addEventListener('change',changed);
  // Network delay is outside the authored 7.5-second sequence. A failed load
  // still reveals the usable homepage instead of trapping the visitor.
  const loadGrace=window.setTimeout(()=>{if(startedAt.current===null)complete();},LOAD_GRACE_MS);
  let frame=0;
  const matchPortalToFilm=()=>{
   const elapsed=video.current?.currentTime??0;
   if(opening.current&&elapsed>=6.75){
    const progress=Math.max(0,Math.min(1,(elapsed-6.75)/.75));
    const halfGap=50*progress;
    const left=50-halfGap,right=50+halfGap;
    const portal=`linear-gradient(90deg,#000 0 ${left}%,transparent ${left}% ${right}%,#000 ${right}% 100%)`;
    opening.current.style.maskImage=portal;
    opening.current.style.setProperty('-webkit-mask-image',portal);
   }
   frame=requestAnimationFrame(matchPortalToFilm);
  };
  frame=requestAnimationFrame(matchPortalToFilm);
  if(motion.matches)complete();
  return()=>{
   window.clearTimeout(loadGrace);if(finishTimer.current!==null)window.clearTimeout(finishTimer.current);cancelAnimationFrame(frame);
   document.body.style.overflow=previousOverflow;home?.removeAttribute('inert');
   document.removeEventListener('keydown',key);motion.removeEventListener('change',changed);
   if(finished.current)requestAnimationFrame(()=>document.getElementById('isabella-main')?.focus());
  };
 },[complete]);

 const play=async()=>{
  const element=video.current;if(!element||finished.current||starting.current||startedAt.current!==null)return;
  starting.current=true;
  try{
   await element.play();
   if(finished.current)return;
   startedAt.current=performance.now();
   // The encoded media clock owns the 7.5-second ending. This deadline is
   // only a safety exit when a device stops advancing an otherwise playable
   // video, so a slow decoder cannot cut the authored final shots short.
   if(!debug)finishTimer.current=window.setTimeout(complete,OPENING_DURATION_MS+7_500);
  }catch{complete();}
 };
 const toggleSound=()=>{
  const element=video.current;if(!element)return;
  const next=!soundOn;element.muted=!next;setSoundOn(next);
  if(next&&startedAt.current!==null&&element.paused)element.play().catch(()=>{element.muted=true;setSoundOn(false);});
 };

 return <div ref={opening} className="lab-opening" role="dialog" aria-modal="true" aria-label="Isabella Labs introduction">
  <video ref={video} className="lab-opening-video" muted playsInline preload="auto" aria-hidden="true"
   src={`/vivacity/isabella-impossible-${format}${lite?'-lite':''}.mp4`}
   onCanPlay={play} onError={complete} onEnded={complete}/>
  <div className="lab-opening-controls">
   <button ref={soundButton} className="lab-opening-control" type="button" onClick={toggleSound} aria-pressed={soundOn}>
    {soundOn?'Sound on':'Sound off'}
   </button>
   <button ref={skip} className="lab-opening-control" type="button" onClick={complete}>Skip intro <span aria-hidden="true">↗</span></button>
  </div>
  {debug&&<label className="lab-opening-debug">Film time <input type="range" min="0" max="7.5" step="0.01" defaultValue="0" onChange={event=>{if(video.current){video.current.pause();video.current.currentTime=Number(event.target.value);}}}/></label>}
 </div>;
}
