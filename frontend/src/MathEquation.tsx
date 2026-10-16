import {useEffect,useRef} from 'react';
import 'katex/dist/katex.min.css';

/** Typeset server-generated math without changing the fitted numbers. */
export default function MathEquation({latex}:{latex:string}){
 const node=useRef<HTMLDivElement>(null);
 useEffect(()=>{
  let cancelled=false;
  import('katex').then(({default:katex})=>{
   if(cancelled||!node.current)return;
   try{katex.render(latex,node.current,{displayMode:true,throwOnError:true,trust:false,output:'htmlAndMathml'});}
   catch{node.current.textContent=latex;}
  }).catch(()=>{if(!cancelled&&node.current)node.current.textContent=latex;});
  return()=>{cancelled=true;};
 },[latex]);
 return <div ref={node} className="factory-math-equation"/>;
}
