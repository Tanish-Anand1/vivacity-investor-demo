import {useCallback,useEffect,useRef,useState} from 'react';
import './labOpening.css';

export const OPENING_DURATION_MS=7500;
const LOAD_GRACE_MS=2300;

export default function LabOpening({finish}:{finish:()=>void}){
 const skip=useRef<HTMLButtonElement>(null);
 const soundButton=useRef<HTMLButtonElement>(null);
 const opening=useRef<HTMLDivElement>(null);
 const video=useRef<HTMLVideoElement>(null);
 const startedAt=useRef(performance.now());
 const playable=useRef(false);
 const finished=useRef(false);
 const [soundOn,setSoundOn]=useState(false);
 const portrait=window.matchMedia('(max-aspect-ratio: 4/5)').matches;
 const connection=(navigator as Navigator&{connection?:{saveData?:boolean;effectiveType?:string}}).connection;
 const lite=connection?.saveData===true||['slow-2g','2g','3g'].includes(connection?.effectiveType??'');
 const format=portrait?'portrait':'landscape';
 const complete=useCallback(()=>{if(finished.current)return;finished.current=true;video.current?.pause();finish();},[finish]);

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
  const deadline=window.setTimeout(complete,OPENING_DURATION_MS+1800);
  // A delayed or unsupported video should reveal the real homepage promptly.
  const loadGrace=window.setTimeout(()=>{if(!playable.current)complete();},LOAD_GRACE_MS);
  let frame=0;
  const matchFadeToFilm=()=>{
   const elapsed=video.current?.currentTime??0;
   if(opening.current&&elapsed>=7){
    const progress=Math.max(0,Math.min(1,(elapsed-7)/.5));
    const edge=100-100*progress;
    opening.current.style.clipPath=`polygon(0 0,${edge}% 0,${edge+4*(1-progress)}% 100%,0 100%)`;
   }
   frame=requestAnimationFrame(matchFadeToFilm);
  };
  frame=requestAnimationFrame(matchFadeToFilm);
  if(motion.matches)complete();
  return()=>{
   window.clearTimeout(deadline);window.clearTimeout(loadGrace);cancelAnimationFrame(frame);
   document.body.style.overflow=previousOverflow;home?.removeAttribute('inert');
   document.removeEventListener('keydown',key);motion.removeEventListener('change',changed);
   if(finished.current)requestAnimationFrame(()=>document.getElementById('isabella-main')?.focus());
  };
 },[complete]);

 const play=()=>{
  const element=video.current;if(!element||finished.current||playable.current)return;
  playable.current=true;
  const elapsed=(performance.now()-startedAt.current)/1000;
  if(element.readyState>=HTMLMediaElement.HAVE_METADATA&&elapsed>.15&&elapsed<7.3)
   element.currentTime=Math.min(elapsed,7.3);
  element.play().catch(complete);
 };
 const toggleSound=()=>{
  const element=video.current;if(!element)return;
  const next=!soundOn;element.muted=!next;setSoundOn(next);
  if(next)element.play().catch(()=>{element.muted=true;setSoundOn(false);});
 };

 return <div ref={opening} className="lab-opening" role="dialog" aria-modal="true" aria-label="Isabella Labs introduction">
  <video ref={video} className="lab-opening-video" autoPlay muted playsInline preload="auto" aria-hidden="true"
   src={`/vivacity/isabella-impossible-${format}${lite?'-lite':''}.mp4`}
   onCanPlay={play} onError={complete} onEnded={complete}/>
  <div className="lab-opening-controls">
   <button ref={soundButton} className="lab-opening-control" type="button" onClick={toggleSound} aria-pressed={soundOn}>
    {soundOn?'Sound on':'Sound off'}
   </button>
   <button ref={skip} className="lab-opening-control" type="button" onClick={complete}>Skip intro <span aria-hidden="true">↗</span></button>
  </div>
 </div>;
}
