"""Measured joint-variable associations with chronological held-out validation.

Closed-loop torque, acceleration and velocity are jointly controlled. A fit is
descriptive and cannot identify inertia, friction or causal mechanisms alone.
"""
import math
import time
from decimal import Decimal

import numpy as np


def _scores(actual,predicted,reference_variation=0.):
    residual=actual-predicted
    mse=float(np.mean(residual*residual))
    total=float(np.sum((actual-np.mean(actual))**2))
    return {'rmse':math.sqrt(mse),'mae':float(np.mean(np.abs(residual))),
            'r2':1-float(np.sum(residual*residual))/total if total>max(1e-20,len(actual)*(reference_variation*.05)**2) else None}


def infer_joint_torque(rows,run_id):
    """Compare constant, acceleration-only and acceleration+velocity fits.

    ``rows`` remain in time order; model selection never sees the held-out
    final fifth of the measured series during coefficient fitting.
    """
    points=[]
    for stamp,values in rows:
        components=(values.get('torque'),values.get('joint_acceleration'),values.get('joint_velocity'))
        if all(value is not None and math.isfinite(float(value)) for value in components):
            points.append((float(stamp),*(float(v) for v in components)))
    base={'schema_version':'vivacity.factory-relationship/1.0','name':'joint_1_torque_vs_dynamics',
          'run_id':run_id,'sample_count':len(points),'updated_at':time.time(),
          'dependent':{'quantity':'joint_1_torque','unit':'N m'},
          'independent':[{'quantity':'joint_1_acceleration','unit':'rad/s²'},
                         {'quantity':'joint_1_velocity','unit':'rad/s'}],
          'provenance':{'source':'MuJoCo joint torque, acceleration and velocity from the same recorded run',
                        'run_id':run_id,'joint_index':0,'split':'first 80% training; final 20% held out'},
          'scope':'Measured association under this controller and these conditions; not a causal or motor-identification result.'}
    if len(points)<50:
        return base|{'status':'insufficient_signal','reason':'At least 50 complete joint measurements are required.','models':[],'selected_model':None}
    values=np.asarray(points,dtype=float)
    split=max(40,int(len(values)*.8))
    train,test=values[:split],values[split:]
    if float(np.std(train[:,1]))<1e-6 or float(np.std(train[:,2]))<1e-6:
        return base|{'status':'insufficient_signal','reason':'Joint torque or acceleration did not vary enough to estimate an association.','models':[],'selected_model':None}
    baseline=float(np.mean(train[:,1]))
    baseline_rmse=_scores(test[:,1],np.full(len(test),baseline))['rmse']
    models=[]
    for name,indices in [('acceleration',[2]),('acceleration_and_velocity',[2,3])]:
        if any(float(np.std(train[:,index]))<1e-6 for index in indices):
            continue
        means=np.mean(train[:,indices],axis=0);scales=np.std(train[:,indices],axis=0)
        design=np.column_stack((np.ones(len(train)),(train[:,indices]-means)/scales))
        condition=float(np.linalg.cond(design))
        if not math.isfinite(condition) or condition>1000:
            continue
        standardized=np.linalg.lstsq(design,train[:,1],rcond=None)[0]
        slopes=standardized[1:]/scales
        intercept=float(standardized[0]-np.sum(slopes*means))
        coefficients=[intercept,*map(float,slopes)]
        predict=lambda rows:intercept+np.asarray(rows[:,indices])@slopes
        training=_scores(train[:,1],predict(train));validation=_scores(test[:,1],predict(test),float(np.std(train[:,1])))
        if not all(math.isfinite(v) for v in (training['rmse'],validation['rmse'])):
            continue
        status='validated_association' if (validation['r2'] is not None and validation['r2']>=.25
            and validation['rmse']<baseline_rmse*.9
            and validation['rmse']<=1.5*training['rmse']+.1*float(np.std(train[:,1]))) else 'poor_fit'
        equation=f'τ = {intercept:.6g} + ({slopes[0]:.6g})×α'
        if len(slopes)>1:equation+=f' + ({slopes[1]:.6g})×ω'
        number=lambda value:format(Decimal(format(float(value),'.8g')),'f')
        latex=r'\tau='+number(intercept)
        for slope,symbol in zip(slopes,(r'\alpha',r'\omega')):
            latex+=(' - ' if slope<0 else ' + ')+number(abs(slope))+symbol
        models.append({'model':name,'coefficients':coefficients,'equation_text':equation,
                       'equation_latex':latex,
                       'training':training,'validation':validation,'condition_number':condition,
                       'validation_status':status,
                       'selection_score':validation['rmse']+float(np.std(train[:,1]))*1e-4*len(coefficients)})
    models.sort(key=lambda row:(row['validation_status']!='validated_association',row['selection_score']))
    selected=models[0] if models else None
    return base|{'status':selected['validation_status'] if selected else 'insufficient_signal',
                 'reason':'Held-out association is descriptive; controller feedback and correlated inputs limit interpretation.' if selected else 'Input variables are too collinear for a stable fit.',
                 'train_count':len(train),'held_out_count':len(test),'baseline_validation_rmse':baseline_rmse,
                 'models':models,'selected_model':selected['model'] if selected else None}
