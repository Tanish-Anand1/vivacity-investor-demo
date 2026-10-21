import {useMemo} from 'react';

export type OrbitSeries={id:string;label:string;predicted_positions:number[][]};
type Props={
  observations:number[][];
  series:OrbitSeries[];
  selectedId:string;
  sampleIndex:number;
  trainCount:number;
  perturbingPosition?:number[];
  className?:string;
};

export default function SciencePlot({observations,series,selectedId,sampleIndex,trainCount,perturbingPosition,className=''}:Props){
  const width=780,height=570,padding=66;
  const points=[...observations,...series.flatMap(item=>item.predicted_positions),...(perturbingPosition?[perturbingPosition]:[])].filter(point=>point.length>=2&&point.every(Number.isFinite));
  const maxX=Math.max(1.25,...points.map(point=>Math.abs(point[0]))),maxY=Math.max(1.25,...points.map(point=>Math.abs(point[1])));
  const scale=Math.min((width-2*padding)/(2*maxX),(height-2*padding)/(2*maxY));
  const xy=(point:number[])=>[width/2+point[0]*scale,height/2-point[1]*scale];
  const path=(position:number[][])=>position.filter(point=>point.length>=2&&point.every(Number.isFinite)).map((point,index)=>`${index?'L':'M'}${xy(point).map(v=>v.toFixed(2)).join(' ')}`).join(' ');
  const chosen=series.find(item=>item.id===selectedId)??series[0];
  const index=Math.max(0,Math.min(observations.length-1,sampleIndex));
  const observed=observations[index],predicted=chosen?.predicted_positions[index];
  const current=predicted?xy(predicted):null;
  const label=useMemo(()=>`Nondimensional orbital observations and computed model trajectories. ${observations.length} samples; ${trainCount} used for fitting and ${Math.max(0,observations.length-trainCount)} held out. Selected model: ${chosen?.label??'none'}.`,[observations.length,trainCount,chosen?.label]);
  return <svg className={`science-plot ${className}`} viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label}>
    <defs>
      <pattern id="science-grid" width="52" height="52" patternUnits="userSpaceOnUse"><path d="M 52 0 L 0 0 0 52" fill="none" stroke="#a8aea21c" strokeWidth="1"/></pattern>
      <radialGradient id="science-core"><stop offset="0" stopColor="#f4e2ba"/><stop offset=".45" stopColor="#c7a875"/><stop offset="1" stopColor="#c7a875" stopOpacity="0"/></radialGradient>
    </defs>
    <rect width={width} height={height} fill="url(#science-grid)"/>
    <line x1={width/2} x2={width/2} y1="24" y2={height-24} stroke="#a8aea242" strokeWidth="1"/>
    <line x1="24" x2={width-24} y1={height/2} y2={height/2} stroke="#a8aea242" strokeWidth="1"/>
    <circle cx={width/2} cy={height/2} r="34" fill="url(#science-core)"/>
    <circle cx={width/2} cy={height/2} r="5" fill="#f8e0aa"/>
    {series.map(item=><path key={item.id} d={path(item.predicted_positions)} fill="none" stroke={item.id===selectedId?'#f3b482':'#b3beb7'} strokeWidth={item.id===selectedId?3:1.7} opacity={item.id===selectedId?1:.5} strokeDasharray={item.id===selectedId?undefined:'7 8'}/>)}
    {observations.map((point,i)=>{const [x,y]=xy(point);return <circle key={i} cx={x} cy={y} r={i>=trainCount?3.6:2.1} fill={i>=trainCount?'#d4e4e2':'#9caea5'} opacity={i>=trainCount?.95:.58}/>;})}
    {perturbingPosition&&<g transform={`translate(${xy(perturbingPosition).join(' ')})`}><circle r="10" fill="none" stroke="#f3b482" strokeWidth="1.5" strokeDasharray="2 3"/><circle r="2.5" fill="#f3b482"/></g>}
    {current&&<g><circle cx={current[0]} cy={current[1]} r="15" fill="#f3b482" opacity=".14"/><circle cx={current[0]} cy={current[1]} r="5.5" fill="#f3b482" stroke="#15201e" strokeWidth="2"/></g>}
    {observed&&<circle cx={xy(observed)[0]} cy={xy(observed)[1]} r="5" fill="#f0f1e9" stroke="#15201e" strokeWidth="2"/>}
    <text x="28" y="35" fill="#a5b5ae" fontSize="11" letterSpacing="2">Y</text>
    <text x={width-28} y={height-28} textAnchor="end" fill="#a5b5ae" fontSize="11" letterSpacing="2">X</text>
  </svg>;
}
