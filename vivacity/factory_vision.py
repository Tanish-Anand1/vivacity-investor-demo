"""RGB + depth + semantic ID render from an actual MuJoCo camera.

Semantic labels are simulator annotations, not a trained perception model.
Metric depth is back-projected with camera intrinsics/extrinsics. The optional
centre estimate assumes a configured upright box; confidence is not invented.
"""
import base64
import struct
import zlib
import mujoco as mj
import numpy as np


def png_bytes(rgb):
    height,width,_=rgb.shape
    def chunk(kind,data):return struct.pack('>I',len(data))+kind+data+struct.pack('>I',zlib.crc32(kind+data)&0xffffffff)
    rows=b''.join(b'\0'+row.tobytes() for row in rgb)
    return b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>2I5B',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(rows))+chunk(b'IEND',b'')


def observe_camera(w,width=320,height=240):
    m,d=w.model,w.data
    mj.mj_forward(m,d)
    w.force_time=float(d.time)
    camera=m.camera('inspection').id;rotation=d.cam_xmat[camera].reshape(3,3).copy();origin=d.cam_xpos[camera].copy()
    focal=.5*height/np.tan(np.deg2rad(float(m.cam_fovy[camera]))/2)
    with mj.Renderer(m,height=height,width=width,max_geom=2000) as renderer:
        option=mj.MjvOption();option.geomgroup[:]=1
        renderer.update_scene(d,camera='inspection',scene_option=option)
        rgb=renderer.render().copy()
        renderer.enable_depth_rendering();depth=renderer.render().copy()
        renderer.disable_depth_rendering();renderer.enable_segmentation_rendering();labels=renderer.render().copy()
    detections=[]
    for i in range(w.config['carton_count']):
        name='target' if i==0 else f'carton_{i}';geom=m.geom('cube' if i==0 else name).id
        mask=(labels[:,:,0]==geom)&(labels[:,:,1]==int(mj.mjtObj.mjOBJ_GEOM))
        y,x=np.nonzero(mask);point=(d.body(name).xpos-origin)@rotation
        projected=[float(width/2+point[0]*focal/-point[2]),float(height/2-point[1]*focal/-point[2])] if point[2]<0 else None
        in_view=projected is not None and 0<=projected[0]<width and 0<=projected[1]<height
        detection={'id':name,'detected':bool(len(x)),'visible_pixels':len(x),'confidence':None,
                   'visibility':'visible' if len(x) else 'occluded' if in_view else 'outside_view',
                   'bbox_xyxy_px':None,'estimated_visible_surface_m':None,'estimated_center_m':None}
        if len(x):
            distance=depth[y,x]
            rays=np.column_stack(((x+.5-width/2)/focal,-(y+.5-height/2)/focal,-np.ones(len(x))))
            points=(rays*distance[:,None])@rotation.T+origin
            surface=np.median(points,axis=0);centre=surface.copy();centre[2]-=w.config['carton_half_size_m']
            detection.update(bbox_xyxy_px=[int(x.min()),int(y.min()),int(x.max()+1),int(y.max()+1)],
                             estimated_visible_surface_m=surface.tolist(),estimated_center_m=centre.tolist())
        detections.append(detection)
    return {'schema_version':'vivacity.factory-camera/1.0','time_s':float(d.time),
            'image_data_url':'data:image/png;base64,'+base64.b64encode(png_bytes(rgb)).decode(),
            'width_px':width,'height_px':height,'focal_length_px':float(focal),'camera_position_m':origin.tolist(),
            'camera_rotation_world':rotation.tolist(),'detections':detections,
            'source':'MuJoCo RGB/depth/semantic rendering',
            'method':'Simulator semantic IDs + metric depth back-projection; not a learned detector',
            'centre_assumption':'Visible surface median minus configured upright box half-height. Occlusion may bias this estimate.',
            'confidence':None}
