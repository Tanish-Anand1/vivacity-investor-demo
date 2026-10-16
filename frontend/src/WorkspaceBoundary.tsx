import {Component,type ReactNode} from 'react';
/** Failed lazy chunks must leave a usable recovery action instead of a white page. */
export default class WorkspaceBoundary extends Component<{children:ReactNode},{failed:boolean}>{
 state={failed:false};static getDerivedStateFromError(){return {failed:true};}
 render(){return this.state.failed?<main className="library-area"><h1>The workspace could not load.</h1><p role="alert">A required interface module failed to load. Your saved server experiments are retained. Reload to reconnect.</p><button className="primary" onClick={()=>window.location.reload()}>Reload workspace</button></main>:this.props.children;}
}
