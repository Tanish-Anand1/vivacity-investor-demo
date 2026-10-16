import type {FactoryFrame,FactoryRun} from './factoryApi';
export type Quantity='x'|'y'|'z'|'speed'|'acceleration'|'torque'|'force'|'power'|'work'|'positive_work'|'kinetic'|'potential'|'conveyor'|'completed'|'throughput';
export const units:Record<Quantity,string>={x:'m',y:'m',z:'m',speed:'m/s',acceleration:'m/s²',torque:'Nm',force:'N',power:'W',work:'J',positive_work:'J',kinetic:'J',potential:'J',conveyor:'m/s',completed:'cartons',throughput:'cartons/min'};
const norm=(v:number[]|undefined)=>v?Math.hypot(...v):null;
export function sampleValue(frame:FactoryFrame,quantity:Quantity,object='target',joint=0,events:FactoryRun['events']=[]):number|null{
 const carton=frame.cartons.find(c=>c.id===object),measure=frame.measurements,physical=measure?.objects.find(c=>c.id===object);
 const completed=events.filter(e=>e.kind==='destination_arrival'&&e.time_s<=frame.time).length;
 const value=({x:carton?.position_m[0],y:carton?.position_m[1],z:carton?.position_m[2],speed:norm(carton?.linear_velocity_m_s),acceleration:norm(physical?.linear_acceleration_m_s2),torque:measure?.robot.joint_torque_nm[joint],force:measure?.robot.gripper_contact_normal_force_n,power:measure?.actuator_power_w,work:measure?.mechanical_work_j,positive_work:measure?.positive_actuator_work_j,kinetic:physical?.kinetic_energy_j,potential:physical?.potential_energy_j,conveyor:frame.conveyors.infeed?.surface_speed_m_s,completed,throughput:frame.time>0?completed*60/frame.time:0})[quantity];
 return typeof value==='number'&&Number.isFinite(value)?value:null;
}
export function nearestSample(frames:FactoryFrame[],time:number){
 if(!frames.length)return -1;
 let low=0,high=frames.length-1;while(low<high){const mid=Math.floor((low+high)/2);if(frames[mid].time<time)low=mid+1;else high=mid;}
 return low>0&&Math.abs(frames[low-1].time-time)<Math.abs(frames[low].time-time)?low-1:low;
}
export function samplesCSV(frames:FactoryFrame[],object:string,joint:number,events:FactoryRun['events']){
 const quantities:Quantity[]=['x','y','z','speed','acceleration','torque','force','power','work','positive_work','kinetic','potential','conveyor','completed','throughput'];
 return ['time_s,'+quantities.map(q=>q+' ['+units[q]+']').join(','),...frames.map(f=>[f.time,...quantities.map(q=>sampleValue(f,q,object,joint,events)??'')].join(','))].join('\r\n');
}
