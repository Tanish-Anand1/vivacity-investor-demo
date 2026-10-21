import {useCallback,useEffect,useRef} from 'react';
import OpeningFigures from './OpeningFigures';
import './labOpening.css';

export const OPENING_DURATION_MS=7500;

export default function LabOpening({finish}:{finish:()=>void}){
 const skip=useRef<HTMLButtonElement>(null);
 const finished=useRef(false);
 const complete=useCallback(()=>{if(finished.current)return;finished.current=true;finish();},[finish]);
 useEffect(()=>{
  const previousOverflow=document.body.style.overflow;
  const home=document.querySelector<HTMLElement>('.isabella-home');
  const media=window.matchMedia('(prefers-reduced-motion: reduce)');
  document.body.style.overflow='hidden';home?.setAttribute('inert','');skip.current?.focus();
  const key=(event:KeyboardEvent)=>{if(event.key==='Escape'){event.preventDefault();complete();}else if(event.key==='Tab'){event.preventDefault();skip.current?.focus();}};
  const changed=()=>{if(media.matches)complete();};
  document.addEventListener('keydown',key);media.addEventListener('change',changed);
  const timer=window.setTimeout(complete,OPENING_DURATION_MS);
  if(media.matches)complete();
  return()=>{window.clearTimeout(timer);document.body.style.overflow=previousOverflow;home?.removeAttribute('inert');document.removeEventListener('keydown',key);media.removeEventListener('change',changed);if(finished.current)requestAnimationFrame(()=>document.getElementById('isabella-main')?.focus());};
 },[complete]);
 return <div className="lab-opening" role="dialog" aria-modal="true" aria-label="Isabella Labs introduction">
  <div className="lab-opening-film" aria-hidden="true">
   <OpeningFigures/>
   <div className="lab-opening-scene"><img src="/vivacity/isabella-intro-cell.webp" alt="" fetchPriority="high"/></div>
   <div className="lab-opening-scanner"/>
   <div className="lab-opening-chapter lab-opening-chapter-world"><span>01 / GIVE IT A</span><strong>WORLD.</strong></div>
   <div className="lab-opening-chapter lab-opening-chapter-change"><span>02 / CHANGE ONE</span><strong>THING.</strong></div>
   <div className="lab-opening-chapter lab-opening-chapter-holds"><span>03 / SEE WHAT</span><strong>HOLDS.</strong></div>
   <div className="lab-opening-brand"><strong>ISABELLA<br/>LABS</strong><span>BY VIVACITY</span></div>
  </div>
  <button ref={skip} className="lab-opening-skip" onClick={complete}>Skip intro <span aria-hidden="true">↗</span></button>
 </div>;
}
