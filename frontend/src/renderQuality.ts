export type RenderQuality='performance'|'balanced'|'high';
export const qualityProfiles={
 performance:{label:'Performance',splats:100000,pixelRatio:1,detail:.6,renderScale:2},
 balanced:{label:'Balanced',splats:300000,pixelRatio:1.25,detail:1,renderScale:1.5},
 high:{label:'High fidelity',splats:500000,pixelRatio:1.5,detail:1.5,renderScale:1},
} as const;
export function defaultQuality(memory?:number,cores?:number):RenderQuality{
 return (memory!==undefined&&memory<=4)||(cores!==undefined&&cores<=4)?'performance':'balanced';
}
export function visualStages(quality:RenderQuality,available:string[]=[]):('100k'|'500k')[]{
 if(available.includes('100k'))return quality!=='performance'&&available.includes('500k')?['100k','500k']:['100k'];
 return ['500k'];
}
