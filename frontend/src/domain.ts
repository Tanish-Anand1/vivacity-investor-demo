import type { components } from './generated/api';
export type Backend = 'mujoco' | 'cloth';
export type World = components['schemas']['WorldResponse'];
export type Experiment = components['schemas']['ExperimentResponse'];
export type Vec3 = [number, number, number];
export type Quat = [number, number, number, number];
export type Dict = Record<string, unknown>;
export interface SimulatedPerception {
  schema_version: 'vivacity.perception/1.0';
  method: 'mujoco_overhead_semantic_depth_rays';
  scope: string;
  ray_count: number;
  visible_cube_rays: number;
  detected: boolean;
  estimated_xy_m: number[] | null;
  localization_error_m: number | null;
  visible_samples_xy_m: number[][];
}
export interface BodyPose { name: string; position: Vec3; quaternion_wxyz: Quat }
export interface Contact { bodies: string[]; geoms: string[]; penetration_m: number; category: string }
export interface RobotFrame {
  inspection?:import('./EngineeringPanel').Inspection;
  environment_geometries?: {name:string;type:string;position:Vec3;quaternion_wxyz:number[];size:Vec3;rgba:number[]}[];
  time: number; qpos: number[]; qvel: number[]; ctrl: number[];
  end_effector: Vec3; body_transforms: BodyPose[];
  target_pose: { position: Vec3; rotation_matrix: number[][] }; contacts: Contact[];
}
export interface ClothFrame { time:number; vertices:Vec3[]; triangles:number[][]; clamp_position:Vec3; clamp_quaternion_wxyz?:Quat; body_transforms?:BodyPose[]; qpos?:number[]; qvel?:number[]; ctrl?:number[]; grasp_active:boolean[]; scope:string }
export type Frame = RobotFrame | ClothFrame;
export interface Evaluation {
  grasp_established?:boolean; lifted?:boolean; retained_during_transport?:boolean; released?:boolean; table_supported?:boolean; max_cube_height_m?:number;
  status: string; success: boolean; planning_feasible?: boolean;
  goal_error_m?: number; orientation_error_rad?: number; execution_duration_s?: number;
  joint_path_length_rad?: number;
  milestone?:string; alignment_error_m?:number; vertex_coverage?:number; grasp_valid?:boolean; grasp_constraint_error_m?:number; fold_quality?:number;
  contact_violations?: Contact[]; failure?: string | null;
  fit_message?: string; phase?: string; error_type?: string;
}
export type Branch = Omit<components['schemas']['BranchResponse'], 'evaluation' | 'trace'> & {
  evaluation: Evaluation; trace: Frame[];
};
export interface ReplayBranch { branch_id: string; source: string; frames: Frame[]; evaluation: Evaluation }
export type Replay = Omit<components['schemas']['ReplayResponse'], 'branches'> & { branches: ReplayBranch[] };
// WebSocket envelopes are not part of REST OpenAPI. Matches EventResponse in
// vivacity/schemas.py and the versioned WebSocket contract in docs/API.md.
export interface Event { schema_version:'1.0'; seq:number; kind:'queued'|'running'|'planned'|'progress'|'branch_completed'|'completed'|'failed'|'cancelled'; details:Dict }
export const format = (n: unknown, digits = 3) => typeof n === 'number' && Number.isFinite(n) ? n.toFixed(digits) : '—';
export const number = (d: Dict | undefined, key: string) => typeof d?.[key] === 'number' ? d[key] as number : undefined;
export function robotFrame(value: unknown): RobotFrame | null {
  const v = value as RobotFrame | null;
  return v && Array.isArray(v.body_transforms) && Array.isArray(v.end_effector) ? v : null;
}
export function simulatedPerception(value: unknown): SimulatedPerception | null {
  const v = value as SimulatedPerception | null;
  return v?.schema_version === 'vivacity.perception/1.0' && Array.isArray(v.visible_samples_xy_m) ? v : null;
}
export function clothFrame(value:unknown):ClothFrame|null {
  const v=value as ClothFrame|null;
  return v&&Array.isArray(v.vertices)&&Array.isArray(v.triangles)?v:null;
}
