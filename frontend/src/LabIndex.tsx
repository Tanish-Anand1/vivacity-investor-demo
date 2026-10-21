import recorded from './generated/isabellaSciencePreview.json';
import './labIndex.css';

export default function LabIndex({openScience,openRobotics,openWorlds}:{openScience:()=>void;openRobotics:()=>void;openWorlds:()=>void}){
 const central=recorded.hypotheses[0].heldout_rmse,expanded=recorded.hypotheses[1].heldout_rmse;
 return <section className="lab-index" aria-labelledby="lab-index-title">
  <div className="lab-index-hero"><p>ISABELLA LABS / BY VIVACITY</p><h1 id="lab-index-title">Choose a world.<br/><span>Test what happens.</span></h1><span>Start with a real simulation, change one meaningful condition, and inspect the outcome.</span></div>
  <div className="lab-index-cases">
   <article className="lab-index-case lab-index-case-robotics"><div className="lab-index-number">01 / ROBOTICS</div><div><h2>A package loses its grip.</h2><p>Enter a robotic workcell. Watch a contact failure, change the gripper force, and compare independently executed runs.</p><div className="lab-index-facts"><span>Physical interaction</span><span>Independent trials</span><span>Recorded replay</span></div><button onClick={openRobotics}>Open robotics lab <span aria-hidden="true">↗</span></button></div><aside className="lab-index-visual"><img src="/vivacity/isabella-scene-poster.webp" alt="Recorded robotic handling workcell"/><span>RECORDED SIMULATION</span></aside></article>
   <article className="lab-index-case"><div className="lab-index-number">02 / NUMERICAL EXPERIMENT</div><div><h2>The Invisible Planet</h2><p>Test whether one physical model can predict an observed orbit better than another. Generate observations, fit both models, and inspect the held-out result.</p><div className="lab-index-facts"><span>Two hypotheses</span><span>Independent fits</span><span>Held-out prediction</span></div><button onClick={openScience}>Open scientific lab <span aria-hidden="true">↗</span></button></div><aside aria-label="Saved numerical comparison"><span>RECORDED EXAMPLE</span><strong>{expanded.toFixed(5)}</strong><small>additional influence · held-out error</small><p>Central-only model: {central.toFixed(5)}. These are saved computed results, not a new run.</p></aside></article>
  </div>
  <div className="lab-index-foot"><p>Change the world, change the condition, then test again.</p><button onClick={openWorlds}>Explore robotic worlds <span aria-hidden="true">↗</span></button></div>
 </section>;
}
