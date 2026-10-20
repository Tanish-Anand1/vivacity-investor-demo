import {useEffect,useRef,useState} from 'react';
import './labOpening.css';

export const OPENING_DURATION_MS=7500;
const within=(time:number,start:number,end:number)=>Math.max(0,Math.min(1,(time-start)/(end-start)));
const ease=(value:number)=>value*value*(3-2*value);

export default function LabOpening({finish}:{finish:()=>void}){
 const [time,setTime]=useState(0),skip=useRef<HTMLButtonElement>(null);
 useEffect(()=>{
  const start=performance.now(),previousOverflow=document.body.style.overflow;
  const home=document.querySelector<HTMLElement>('.isabella-home');
  let frame=0,completed=false;
  function complete(){if(completed)return;completed=true;finish();}
  function tick(now:number){const elapsed=Math.min(OPENING_DURATION_MS,now-start);setTime(elapsed);if(elapsed>=OPENING_DURATION_MS)complete();else frame=requestAnimationFrame(tick);}
  document.body.style.overflow='hidden';home?.setAttribute('inert','');skip.current?.focus();
  const key=(event:KeyboardEvent)=>{if(event.key==='Escape'){event.preventDefault();complete();}else if(event.key==='Tab'){event.preventDefault();skip.current?.focus();}};
  document.addEventListener('keydown',key);
  const media=window.matchMedia('(prefers-reduced-motion: reduce)');
  if(media.matches)complete();else frame=requestAnimationFrame(tick);
  const changed=()=>{if(media.matches)complete();};media.addEventListener('change',changed);
  return()=>{cancelAnimationFrame(frame);document.body.style.overflow=previousOverflow;home?.removeAttribute('inert');document.removeEventListener('keydown',key);media.removeEventListener('change',changed);};
 },[finish]);
 const question=ease(within(time,260,700))*(1-ease(within(time,1250,2100)));
 const paths=ease(within(time,1200,2700))*(1-ease(within(time,5400,6800)));
 const glimpse=ease(within(time,2700,3500))*(1-ease(within(time,4500,5150)));
 const name=ease(within(time,4500,5150))*(1-ease(within(time,6350,7350)));
 const reveal=ease(within(time,6200,7500));
 const windowAmount=ease(within(time,2700,3250))*(1-ease(within(time,4300,4500)));
 const openingEdge=100-58*windowAmount;
 return <div className="lab-opening" role="dialog" aria-modal="true" aria-label="Isabella Labs introduction" data-opening-ms={Math.floor(time)}>
  <div className="lab-opening-curtain" style={{opacity:1-reveal,clipPath:`polygon(0 0, ${openingEdge+10}% 0, ${openingEdge}% 100%, 0 100%)`}} aria-hidden="true"/>
  <div className="lab-opening-top-mask" style={{opacity:1-reveal}} aria-hidden="true"/>
  <svg className="lab-opening-sculpture" viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid slice" aria-hidden="true" style={{opacity:1-reveal}}>
   <defs><linearGradient id="isabella-metal" x1="0" x2="1" y1="0" y2="1"><stop stopColor="#d8dcd7"/><stop offset=".43" stopColor="#46524e"/><stop offset=".64" stopColor="#a8b3aa"/><stop offset="1" stopColor="#1b2421"/></linearGradient></defs>
   <path className="isabella-mass" d="M-210 700 C170 660 400 580 606 452 C655 423 700 411 745 420" fill="none" stroke="url(#isabella-metal)" strokeWidth="92" strokeLinecap="square" style={{strokeDasharray:1150,strokeDashoffset:1150*(1-ease(within(time,0,1200))),opacity:1-ease(within(time,2700,3200))}}/>
   <path d="M730 422 C950 364 1080 212 1660 68" stroke="#c1ccc3" strokeWidth="3" fill="none" strokeDasharray="1250" style={{strokeDashoffset:1250*(1-ease(within(time,1200,2700))),opacity:paths}}/>
   <path d="M730 422 C966 427 1114 447 1660 486" stroke="#d8e0d8" strokeWidth="3" fill="none" strokeDasharray="1250" style={{strokeDashoffset:1250*(1-ease(within(time,1300,2700))),opacity:paths}}/>
   <path d="M730 422 C924 505 1120 642 1670 846" stroke="#899f91" strokeWidth="3" fill="none" strokeDasharray="1250" style={{strokeDashoffset:1250*(1-ease(within(time,1400,2700))),opacity:paths}}/>
   <path d="M730 422 C906 393 1050 288 1425 350 C1500 370 1560 400 1660 460" stroke="#788b82" strokeWidth="1.5" fill="none" strokeDasharray="1250" style={{strokeDashoffset:1250*(1-ease(within(time,1500,2700))),opacity:paths*.8}}/>
   <path d="M1060 245 C1180 322 1280 415 1600 452 M1060 601 C1200 510 1410 455 1600 452" fill="none" stroke="#e7ede5" strokeWidth="2" strokeDasharray="900" style={{strokeDashoffset:900*(1-ease(within(time,4500,6100))),opacity:name}}/>
  </svg>
  <div className="lab-opening-copy lab-opening-question" style={{opacity:question,transform:`translate3d(0,${(1-question)*28}px,0)`}}><h1>What if?</h1></div>
  <div className="lab-opening-copy lab-opening-glimpse" style={{opacity:glimpse,transform:`translate3d(0,${(1-glimpse)*35}px,0)`}}><h1>Explore what<br/><em>could be.</em></h1></div>
  <div className="lab-opening-name" style={{opacity:name,transform:`translate(-50%,-50%) scale(${.84+.16*name})`}}><strong>ISABELLA<br/>LABS</strong><span>BY VIVACITY</span></div>
  <button ref={skip} className="lab-opening-skip" onClick={finish}>Skip intro <span aria-hidden="true">↗</span></button>
 </div>;
}
