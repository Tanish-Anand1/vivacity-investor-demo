import recorded from './generated/isabellaSciencePreview.json';
import './labIndex.css';

export default function LabIndex({openScience,openRobotics,openWorlds}:{openScience:()=>void;openRobotics:()=>void;openWorlds:()=>void}){
 const central=recorded.hypotheses[0].heldout_rmse,expanded=recorded.hypotheses[1].heldout_rmse;
 return <section className="lab-index" aria-labelledby="lab-index-title">
  <div className="lab-index-hero"><p>ISABELLA LABS / BY VIVACITY</p><h1 id="lab-index-title">Choose a question.<br/><em>Enter its world.</em></h1><span>Each lab runs on a real numerical or physical simulation backend. Change the conditions, compare independent branches, and inspect what the calculation actually found.</span></div>
  <div className="lab-index-cases">
   <article className="lab-index-case"><div className="lab-index-number">01 / SCIENTIFIC INFERENCE</div><div><h2>The Invisible Planet</h2><p>Is a central gravitational force enough to explain a measured orbit? Generate observations, fit two models with SciPy, and test them against held-out positions.</p><div className="lab-index-facts"><span>2D restricted gravity</span><span>2 competing hypotheses</span><span>Held-out prediction</span></div><button onClick={openScience}>Open discovery lab <span aria-hidden="true">↗</span></button></div><aside aria-label="Recorded example held-out error"><span>RECORDED EXAMPLE</span><strong>{expanded.toFixed(5)}</strong><small>additional influence · held-out RMSE</small><p>Central-only model: {central.toFixed(5)}. Values from a saved SciPy computation, not a new run.</p></aside></article>
   <article className="lab-index-case"><div className="lab-index-number">02 / ROBOTIC EXPERIMENTATION</div><div><h2>A package loses its grip.</h2><p>Watch a simulated robot fail to deliver a carton, change the gripper force, and compare matched MuJoCo trials. Inspect the contact-driven result and replay recorded states.</p><div className="lab-index-facts"><span>MuJoCo dynamics</span><span>Independent starts</span><span>Measured delivery</span></div><button onClick={openRobotics}>Open robotics lab <span aria-hidden="true">↗</span></button></div><aside aria-label="Physical experiment scope"><span>SIMULATED WORKCELL</span><strong>MuJoCo</strong><small>Franka Panda · conveyor cell</small><p>Recorded outcomes describe simulation. Hardware reliability remains unvalidated.</p></aside></article>
  </div>
  <div className="lab-index-foot"><p>Worlds can be configured and revisited. Results remain attached to the world version and simulator that produced them.</p><button onClick={openWorlds}>Explore robotic worlds <span aria-hidden="true">↗</span></button></div>
 </section>;
}
