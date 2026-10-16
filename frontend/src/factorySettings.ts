import type {FactorySettings} from './factoryApi';

/** Older saved cells may lack fields added to the editable configuration. */
export function editableFactorySettings(defaults:FactorySettings,saved:Partial<FactorySettings>):FactorySettings{
 return {...defaults,...saved};
}

const numericBounds:Partial<Record<keyof FactorySettings,[string,number,number,boolean]>>={
 carton_count:['Cartons',1,3,true],carton_start_x_m:['Initial carton X (m)',.465,.535,false],carton_start_y_m:['Initial carton Y (m)',-1.28,-.35,false],
 carton_mass_kg:['Reference mass (kg)',.02,.15,false],carton_half_size_m:['Carton half-width (m)',.02,.03,false],carton_friction:['Contact friction',.05,1.5,false],
 conveyor_speed_m_s:['Conveyor speed (m/s)',.02,.18,false],arrival_interval_s:['Minimum arrival spacing (s)',1,60,true],sort_threshold_kg:['Lane threshold (kg)',.02,.15,false],
 realtime_speed:['Simulation speed',.25,8,false],gripper_force_scale:['Gripper force scale',.005,1,false],
};

/** Reject incomplete or out-of-range draft values before they can become JSON nulls or API errors. */
export function factorySettingsIssue(settings:FactorySettings):string|null{
 if(!settings.name.trim())return 'Enter a configuration name.';
 for(const [key,[label,min,max,integer]] of Object.entries(numericBounds) as [keyof FactorySettings,[string,number,number,boolean]][]){
  const value=settings[key];
  if(typeof value!=='number'||!Number.isFinite(value))return `Enter a valid value for ${label}.`;
  if(value<min||value>max)return `${label} must be between ${min} and ${max}.`;
  if(integer&&!Number.isInteger(value))return `${label} must be a whole number.`;
 }
 return null;
}
