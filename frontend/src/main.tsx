import ReactDOM from 'react-dom/client';
import App from './App';
import WorkspaceBoundary from './WorkspaceBoundary';
import './styles.css';
import './templates.css';
import './refined.css';

ReactDOM.createRoot(document.getElementById('root')!).render(<WorkspaceBoundary><App /></WorkspaceBoundary>);
