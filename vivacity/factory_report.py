"""Engineering publications from saved records; no new simulation or invented values."""
import csv
from datetime import datetime,timezone
import io
import math
from pathlib import Path
from xml.sax.saxutils import escape
from reportlab import rl_config
from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle,PageBreak,Flowable,KeepTogether
from .factory import LAYOUT
from .factory_exchange import METRICS,digest

INK=colors.HexColor('#182624');MUTED=colors.HexColor('#52635f');AMBER=colors.HexColor('#a26420');LINE=colors.HexColor('#ccd4cf')
FONT_PATH=Path(rl_config.TTFSearchPath[0])
# ReportLab's redistributable Bitstream Vera avoids host-font dependencies.
import reportlab
FONT_PATH=Path(reportlab.__file__).parent/'fonts'
for name,file in [('Factory','Vera.ttf'),('FactoryBold','VeraBd.ttf')]:
    if name not in pdfmetrics.getRegisteredFontNames():pdfmetrics.registerFont(TTFont(name,str(FONT_PATH/file)))
STYLES={
 'body':ParagraphStyle('body',fontName='Factory',fontSize=10,leading=15,textColor=INK,spaceAfter=9),
 'small':ParagraphStyle('small',fontName='Factory',fontSize=8,leading=12,textColor=MUTED,spaceAfter=7),
 'h1':ParagraphStyle('h1',fontName='FactoryBold',fontSize=25,leading=31,textColor=INK,spaceAfter=16,keepWithNext=True),
 'h2':ParagraphStyle('h2',fontName='FactoryBold',fontSize=16,leading=22,textColor=INK,spaceBefore=14,spaceAfter=10,keepWithNext=True),
 'label':ParagraphStyle('label',fontName='FactoryBold',fontSize=9,leading=13,textColor=AMBER,spaceAfter=10),
}
def p(value,style='body'):return Paragraph(escape(str(value)),STYLES[style])
def num(value,unit='',digits=3):return 'Unavailable' if value is None else f'{value:.{digits}f}'+(' '+unit if unit else '')

class Plot(Flowable):
    def __init__(self,title,unit,series,height=160):
        Flowable.__init__(self);self.width=499;self.height=height;self.title=title;self.unit=unit;self.series=series
    def draw(self):
        c=self.canv;left=54;bottom=31;right=self.width-14;top=self.height-31
        c.setFont('FactoryBold',10);c.setFillColor(INK);c.drawString(0,self.height-11,self.title)
        c.setFont('Factory',8);c.setFillColor(MUTED);c.drawRightString(self.width,self.height-11,self.unit)
        valid=[(t,v) for t,v in self.series if v is not None and math.isfinite(v)]
        if not valid:c.drawString(left,top-20,'This quantity was not recorded.');return
        times=[r[0] for r in valid];values=[r[1] for r in valid];xmin=min(times);xmax=max(times);ymin=min(values);ymax=max(values)
        if ymax-ymin<1e-10:ymin-=.5;ymax+=.5
        pad=(ymax-ymin)*.06;ymin-=pad;ymax+=pad
        def xy(t,v):return left+(right-left)*(t-xmin)/max(xmax-xmin,1e-9),bottom+(top-bottom)*(v-ymin)/(ymax-ymin)
        for i in range(4):
            y=bottom+(top-bottom)*i/3;c.setStrokeColor(LINE);c.setLineWidth(.4);c.line(left,y,right,y)
            c.setFillColor(MUTED);c.drawRightString(left-7,y-3,f'{ymin+(ymax-ymin)*i/3:.3g}')
        c.drawString(left,13,f'{xmin:.2f}');c.drawRightString(right,13,f'{xmax:.2f} s');c.drawCentredString((left+right)/2,13,'Simulation time')
        path=c.beginPath();pen=False
        # Vector plot retains every stored sample; nulls create visible gaps.
        for t,v in self.series:
            if v is None or not math.isfinite(v):pen=False;continue
            x,y=xy(t,v)
            if pen:path.lineTo(x,y)
            else:path.moveTo(x,y);pen=True
        c.setLineWidth(1.05);c.setStrokeColor(AMBER);c.drawPath(path)

class FactoryPlan(Flowable):
    def __init__(self,frame,height=270):Flowable.__init__(self);self.frame=frame;self.width=499;self.height=height
    def draw(self):
        c=self.canv;scale=79;cx=240;cy=120
        def xy(x,y):return cx+x*scale,cy+y*scale
        c.setFillColor(colors.HexColor('#f0f2ec'));c.rect(0,0,self.width,self.height,stroke=0,fill=1)
        belts=[LAYOUT['infeed'],LAYOUT['transfer'],LAYOUT['shuttle'],*LAYOUT['lanes']]
        for belt in belts:
            x,y=xy(belt['x']-.11,belt['start_y']);w=.22*scale;h=(belt['end_y']-belt['start_y'])*scale
            c.setFillColor(colors.HexColor('#d4dcd5'));c.setStrokeColor(MUTED);c.rect(x,y,w,h,fill=1,stroke=1)
            for j in range(round((belt['end_y']-belt['start_y'])/LAYOUT['roller_spacing'])+1):
                c.setLineWidth(.7);yy=y+j*LAYOUT['roller_spacing']*scale;c.line(x+2,yy,x+w-2,yy)
        poses={b['name']:b['position'] for b in self.frame.get('body_transforms',[])}
        points=[poses[n] for n in ['link0','link1','link2','link3','link4','link5','link6','link7','hand'] if n in poses]
        for a,b in zip(points,points[1:]):
            c.setLineWidth(8);c.setStrokeColor(colors.HexColor('#7b8f88'));c.line(*xy(*a[:2]),*xy(*b[:2]))
        for point in points:
            c.setFillColor(INK);c.circle(*xy(*point[:2]),3,fill=1,stroke=0)
        for carton in self.frame.get('cartons',[]):
            x,y=xy(*carton['position_m'][:2]);c.setFillColor(AMBER);c.rect(x-3,y-3,6,6,fill=1,stroke=0)
        c.setFillColor(MUTED);c.setFont('Factory',9)
        for label,x,y in [('Infeed',.76,-.85),('Panda',-.66,0),('Transfer',.83,.34),('Lane A',-.35,1.16),('Lane B',.92,1.16)]:c.drawString(*xy(x,y),label)
        c.drawString(15,14,'Recorded XY geometry / metres / Z-up');c.drawRightString(self.width-15,14,f"t = {self.frame.get('time',0):.3f} s")

def table(rows,widths=None):
    content=[[p(v,'small') for v in row] for row in rows]
    t=Table(content,colWidths=widths or [249.5,249.5],repeatRows=1,hAlign='LEFT')
    t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.HexColor('#e6ebe5')),('VALIGN',(0,0),(-1,-1),'TOP'),
        ('LINEBELOW',(0,0),(-1,0),.7,INK),('LINEBELOW',(0,1),(-1,-1),.35,LINE),
        ('LEFTPADDING',(0,0),(-1,-1),8),('RIGHTPADDING',(0,0),(-1,-1),8),('TOPPADDING',(0,0),(-1,-1),7),('BOTTOMPADDING',(0,0),(-1,-1),4)]))
    return t

def report_pdf(run,benchmark=None,attribution=None,discovery=None):
    """Return an editorial PDF whose plots and tables use exactly the saved record."""
    out=io.BytesIO();record=benchmark or run;config=run['config'];metrics=run['metrics'];trace=run.get('trace',[])
    title=record.get('name',config['name']);when=datetime.fromtimestamp(record['created_at'],timezone.utc).strftime('%d %B %Y / %H:%M UTC')
    story=[p('VIVACITY  /  PHYSICAL INTELLIGENCE','label'),Spacer(1,12),p('Carton sorting study','h1'),p(title),
           p(when,'small'),FactoryPlan(run.get('frame',{})),Spacer(1,12),
           p('MuJoCo Menagerie Franka Panda / Contact-driven sorting cell','small'),
           p('Project: '+(attribution or {}).get('project','Unassigned')+' / Declared creator: '+(attribution or {}).get('creator',run.get('creator_label') or 'Not recorded'),'small'),
           p('Executive finding','h2')]
    if benchmark:
        completed=sum(t['status']=='completed' for t in benchmark['trials'])
        story.append(p(f"Benchmark status: {benchmark['status']}. {completed} of {len(benchmark['trials'])} recorded trials completed the full sorting task. Training selection: {benchmark['comparison'].get('selected_condition') or 'none'}. Held-out trials are reported separately."))
        story.append(p('Physics figures use the first recorded trial, identified on each analysis page. This choice does not filter for success.','small'))
    else:
        story.append(p(f"Run status: {run['status']}. {metrics.get('cartons_sorted',0)} of {config['carton_count']} configured cartons reached their selected destinations in {num(metrics.get('simulation_time_s'),'s')} of simulation time."))
    story.append(p(run.get('error') or 'The controller used simulated object pose and mass, joint-space planning, position actuation and native frictional contacts. No hardware performance is inferred.'))
    story += [PageBreak(),p('01 / SYSTEM & OUTCOME','label'),p('Conditions and measured results','h1')]
    rows=[['Parameter','Saved value'],['Robot / engine','Franka Panda / MuJoCo '+run['engine']['version']],
          ['World version',run['world_version']],['Seed / timestep',f"{config['seed']} / 0.002 s"],
          ['Cartons / reference mass',f"{config['carton_count']} / {num(config['carton_mass_kg'],'kg')}"],
          ['Box dimensions',num(config['carton_half_size_m']*2,'m')+' on each axis'],
          ['Friction / gripper force scale',f"{config['carton_friction']} / {config['gripper_force_scale']}"],
          ['Conveyor / minimum arrival spacing',f"{num(config['conveyor_speed_m_s'],'m/s')} / {num(config['arrival_interval_s'],'s')}"],
          ['Lane criterion',f"A below {config['sort_threshold_kg']} kg; B otherwise"],
          ['Initial carton X / Y',f"{num(config['carton_start_x_m'],'m')} / {num(config['carton_start_y_m'],'m')}"],
          ['Status / failure category',run['status']+' / '+(run['phase'] if run['status']=='failed' else 'None recorded')],
          ['Verified deliveries / configured batch',f"{metrics.get('cartons_sorted',0)} / {config['carton_count']}"],
          ['Simulation duration / steps',f"{num(metrics.get('simulation_time_s'),'s')} / {metrics.get('simulation_steps','Unavailable')}"],
          ['Wall execution time',num(metrics.get('wall_time_s'),'s')],
          ['Delivered throughput',num(60*metrics.get('cartons_sorted',0)/metrics['simulation_time_s'],'cartons/min') if metrics.get('simulation_time_s') else 'Unavailable']]
    story+=[table(rows,[205,294]),Spacer(1,12),p('Interpretation','h2'),p('Throughput divides verified deliveries by elapsed simulation time. This finite batch is not a steady-state industrial throughput or a hardware cycle-time measurement. A carton counts only after native contact with its mass-selected bin floor.'),p('Gravity is 9.81 m/s²; contacts use MuJoCo friction and compliant constraints. Robot arm gravity compensation is enabled. Object dimensions, friction and mass are configured model inputs, not camera estimates.','small')]
    def measured(f,key):return f.get('measurements',{}).get(key)
    def carton(f):return next((o for o in f.get('cartons',[]) if o['id']=='target'),{})
    def target(f):return next((o for o in f.get('measurements',{}).get('objects',[]) if o['id']=='target'),{})
    def norm(v):return math.sqrt(sum(x*x for x in v)) if v is not None else None
    graphs=[('Carton height','m',lambda f:(carton(f).get('position_m') or [None]*3)[2]),
            ('Carton speed','m/s',lambda f:norm(carton(f).get('linear_velocity_m_s'))),
            ('Carton acceleration magnitude','m/s²',lambda f:norm(target(f).get('linear_acceleration_m_s2'))),
            ('Joint 1 actuator torque','N m',lambda f:(f.get('measurements',{}).get('robot',{}).get('joint_torque_nm') or [None])[0]),
            ('Gripper contact normal force','N',lambda f:f.get('measurements',{}).get('robot',{}).get('gripper_contact_normal_force_n')),
            ('Total actuator mechanical power','W',lambda f:measured(f,'actuator_power_w')),
            ('Net actuator mechanical work','J',lambda f:measured(f,'mechanical_work_j')),
            ('Carton kinetic energy','J',lambda f:target(f).get('kinetic_energy_j'))]
    for page in range(2):
        story += [PageBreak(),p(f'0{page+2} / PHYSICS ANALYSIS','label'),p('Motion and contact' if page==0 else 'Force and mechanical work','h1'),p('Source run '+run['id']+f" / {len(trace)} stored samples",'small')]
        for name,unit,read in graphs[page*4:(page+1)*4]:story.append(Plot(name,unit,[(f['time'],read(f)) for f in trace],height=134))
        story.append(p('Pose time is shown. Forces and acceleration refer to the preceding 2 ms physics solve. Work is accumulated every integration step; other plotted quantities are sampled. Gaps mean unavailable data.','small'))
    series=(discovery or {}).get('series',{})
    if series:
        story += [PageBreak(),p('DISCOVERY / DESCRIPTIVE FITS','label'),p('Equations from saved measurements','h1'),
                  p('Source run '+run['id']+f" / {discovery['sample_count']} persisted scalar samples",'small'),
                  p('Each equation is a fitted approximation to this simulation, not a physical law. Training uses the first 80% of samples; the final 20% is held out in time order.')]
        for quantity in ('x','y','z','speed','torque','force','power','work'):
            series_record=series.get(quantity)
            if not series_record:continue
            selected=next((model for model in series_record.get('models',[]) if model['model']==series_record.get('selected_model')),None)
            story.append(p(series_record['label']+' / '+series_record['unit']+' / '+str(series_record.get('fit_stage') or 'unknown')+' / '+series_record['status'],'label'))
            if selected:
                story.append(p(selected['equation_text'],'small'))
                story.append(p('Held-out RMSE '+num(selected['validation']['rmse'],series_record['unit'],5)
                               +' / MAE '+num(selected['validation']['mae'],series_record['unit'],5)
                               +' / R² '+num(selected['validation']['r2'],digits=3)
                               +' / '+str(series_record.get('sample_count',0))+' measured samples','small'))
            else:story.append(p(series_record.get('reason','No fitted model available.'),'small'))
    story += [PageBreak(),p('04 / MOTION & EVENTS','label'),p('The recorded operation','h1')]
    story.append(Plot('Joint 1 position','rad',[(f['time'],(f.get('qpos') or [None])[0]) for f in trace],135))
    story.append(table([['Simulation time','Recorded event']]+[[num(e['time_s'],'s'),e['kind'].replace('_',' ')] for e in run['events']],[110,389]))
    if benchmark:
        story += [PageBreak(),p('05 / CONTROLLED COMPARISON','label'),p('Repeated trials and held-out evidence','h1'),p(benchmark['definition']['success_criterion']),p(benchmark['definition']['held_out_protocol'],'small')]
        rows=[['Condition / partition','Success','Mean duration','Sample variance']]
        for partition,groups in benchmark['comparison'].get('partitions',{}).items():
            for condition,result in groups.items():rows.append([condition+' / '+partition.replace('_',' '),f"{result['successes']}/{result['trials']}",num(result['successful_duration_mean_s'],'s'),num(result['successful_duration_variance_s2'],'s²')])
        story += [table(rows,[179,60,125,135]),Spacer(1,12),p(benchmark['comparison'].get('selection_reason','No selection available.')),p('Trial outcomes','h2'),table([['Trial / seed','Condition','Outcome']]+[[str(i+1)+' / '+str(t['config']['seed']),t['partition'].replace('_',' ')+' / '+t['condition'],t['failure_kind'] or t['status']] for i,t in enumerate(benchmark['trials'])],[90,210,199]),p(benchmark['comparison'].get('scope','Incomplete benchmark; no complete comparison available.'),'small')]
    story += [PageBreak(),p('APPENDIX / REPRODUCIBILITY','label'),p('Evidence and physical assumptions','h1'),p('Saved record: '+record['id']),p('Record SHA-256: '+digest(record),'small'),p('Native initial model SHA-256: '+run['initial_state']['model_hash'],'small'),p('Full integration state, controls, configuration, events and all stored samples are included in the JSON archive. The ZIP also contains a flat CSV of measured samples. No random data is generated during reporting.')]
    for name,meaning in METRICS.items():story.append(p(name+' — '+meaning))
    story += [p('Physical equations','h2'),p('Actuator mechanical power P = sum(force × actuator velocity). Net work W = sum(P × 0.002 s). Kinetic energy includes translation and rotation; potential energy uses the cell ground plane as its height reference.'),p('Limits and next experiment','h2'),p('Results apply to this small-carton model and its configured controller. They do not establish hardware safety, perception generalization, electrical consumption or industrial uptime. Camera semantic labels are simulator annotations; control uses simulator pose and mass.'),p('Next: compare one physical condition at a time using matched seeds, retain all failures and evaluate the frozen choice on held-out starting positions. More repetitions are needed before making reliability claims.'),p('Report generator: vivacity.factory-report/1.0. Missing or legacy provenance remains unavailable; it is never reconstructed as a claim about a past execution.','small')]
    def footer(c,doc):
        c.setStrokeColor(LINE);c.line(48,42,547,42);c.setFillColor(MUTED);c.setFont('Factory',8)
        c.drawString(48,28,'VIVACITY / Simulation evidence');c.drawRightString(547,28,f'{record["id"][:8]}  /  {doc.page}')
    SimpleDocTemplate(out,pagesize=(595,842),leftMargin=48,rightMargin=48,topMargin=42,bottomMargin=56,
                      title=title,author='Vivacity',pageCompression=1).build(story,onFirstPage=footer,onLaterPages=footer)
    return out.getvalue()

def csv_samples(run):
    stream=io.StringIO(newline='');w=csv.writer(stream)
    w.writerow(['time_s','carton_id','x_m','y_m','z_m','vx_m_s','vy_m_s','vz_m_s','mass_kg','gripper_force_n','power_w','work_j',*[f'joint_{i+1}_torque_nm' for i in range(7)]])
    for frame in run.get('trace',[]):
        m=frame.get('measurements',{});robot=m.get('robot',{})
        for carton in frame.get('cartons',[]):w.writerow([frame['time'],carton['id'],*carton['position_m'],*carton['linear_velocity_m_s'],carton['mass_kg'],robot.get('gripper_contact_normal_force_n'),m.get('actuator_power_w'),m.get('mechanical_work_j'),*robot.get('joint_torque_nm',[None]*7)])
    return stream.getvalue()
