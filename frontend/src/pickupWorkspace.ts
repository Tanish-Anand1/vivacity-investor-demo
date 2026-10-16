import type { Vec3 } from './domain';

export const TABLE_X: readonly [number, number] = [-.3, 1.1];
export const TABLE_Y: readonly [number, number] = [-.65, .65];
export const MIN_PICKUP_SEPARATION_M = .1;

const clamp = (value: number, [min,max]: readonly [number,number]) => Math.max(min,Math.min(max,value));

export function objectHalfSizes(config: {cube_half_sizes?:unknown;cube_half_size?:unknown}): Vec3 {
  const dimensions=config.cube_half_sizes;
  if(Array.isArray(dimensions)&&dimensions.length===3&&dimensions.every(v=>typeof v==='number'))return dimensions as Vec3;
  const half=Number(config.cube_half_size??.025);
  return [half,half,half];
}

export function pickupBounds(halfSizes:Vec3): {x:readonly [number,number];y:readonly [number,number]} {
  return {x:[TABLE_X[0]+halfSizes[0]+.001,TABLE_X[1]-halfSizes[0]-.001],
    y:[TABLE_Y[0]+halfSizes[1]+.001,TABLE_Y[1]-halfSizes[1]-.001]};
}

export function clampPickupPosition(x: number, y: number, halfSizes: Vec3): Vec3 {
  const bounds=pickupBounds(halfSizes);
  return [clamp(x,bounds.x),clamp(y,bounds.y),halfSizes[2]+.001];
}

export function pickupSeparationValid(pickup: readonly number[], placement: readonly number[]): boolean {
  return Math.hypot(pickup[0]-placement[0],pickup[1]-placement[1]) >= MIN_PICKUP_SEPARATION_M-1e-9;
}

export function placementAwayFrom(pickup:Vec3, placement:Vec3, halfSizes:Vec3):Vec3 {
  if(pickupSeparationValid(pickup,placement))return placement;
  const bounds=pickupBounds(halfSizes);
  const options=[pickup[0]+.18,pickup[0]-.18].map(x=>clamp(x,bounds.x));
  const x=options.find(value=>Math.abs(value-pickup[0])>=MIN_PICKUP_SEPARATION_M)??options[0];
  return [x,pickup[1],halfSizes[2]+.001];
}
